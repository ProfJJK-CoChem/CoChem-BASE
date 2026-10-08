#!/usr/bin/env python3
"""Execute the BASE GUI's bounded data-only request on a fresh Actions runner."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request

# Direct script execution starts on scripts/, while the cheap readiness path
# deliberately runs before BASE installation. Import only helpers from this
# exact reviewed checkout, independent of ambient PYTHONPATH or caller cwd.
_CHECKOUT_ROOT = Path(__file__).resolve().parents[1]
if str(_CHECKOUT_ROOT) not in sys.path:
    sys.path.insert(0, str(_CHECKOUT_ROOT))


def _local_contract(name: str):
    path = Path(__file__).resolve().parents[1] / "src/cochem_base/interfaces" / (name + ".py")
    spec = importlib.util.spec_from_file_location("cochem_student_" + name, path)
    if spec is None or spec.loader is None:
        raise ImportError("The reviewed student request contract is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


contract = _local_contract("student_request")


def _atomic_json(path: Path, value: dict) -> None:
    import tempfile
    descriptor, temporary = tempfile.mkstemp(prefix=".student-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contract.canonical_json(value) + b"\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _identity(request: dict) -> dict:
    return {"schema_version": "cochem.student-result/1", "request_id": request["request_id"],
            "repository": request["repository"], "source_sha": request["source_sha"],
            "worker_source_sha": request["worker_source_sha"],
            "payload_sha256": os.environ["REQUEST_SHA256"],
            "run_id": int(os.environ["GITHUB_RUN_ID"]),
            "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "1")),
            "resources": request["resources"], "status": "prepared", "operation_performed": False,
            "created_at": datetime.now(timezone.utc).isoformat()}


def preflight(output: Path) -> dict:
    request = contract.decode_transport_request(os.environ["REQUEST_BASE64"], os.environ["REQUEST_SHA256"])
    if (request["request_id"] != os.environ["REQUEST_ID"]
            or request["repository"] != os.environ["GITHUB_REPOSITORY"]
            or request["source_sha"] != os.environ["GITHUB_SHA"]
            or os.environ["GITHUB_REF"] != "refs/heads/" + os.environ["DEFAULT_BRANCH"]):
        raise ValueError("The request identity, approved default branch or exact source commit has changed; resubmit from BASE")
    output = output.expanduser().resolve()
    source = Path(__file__).resolve().parents[1]
    if output.is_relative_to(source):
        raise ValueError("Hosted evidence must remain outside the source checkout")
    output.mkdir(parents=True, exist_ok=False)
    _atomic_json(output / "request.json", request)
    _atomic_json(output / "student-result.json", _identity(request))
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as stream:
            stream.write(f"worker_sha={request['worker_source_sha']}\n")
    return request


def approve_worker(output: Path) -> dict:
    """Approve only an instructor-controlled canonical revision, never a user ref."""
    request = contract.strict_json((output / "request.json").read_bytes())
    transported = contract.decode_transport_request(os.environ["REQUEST_BASE64"], os.environ["REQUEST_SHA256"])
    if request != transported:
        raise ValueError("The saved request differs from the submitted transport bytes")
    token = os.environ.get("COCHEM_SOURCE_READ_TOKEN", "")
    if not token:
        raise ValueError("The instructor must authorize this assignment for BASE source-reader access")
    canonical = "ProfJJK-CoChem/CoChem-BASE"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect())

    def get(path):
        operation = urllib.request.Request("https://api.github.com/repos/" + canonical + path,
            headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                     "User-Agent": "CoChem-BASE-approved-worker", "X-GitHub-Api-Version": "2022-11-28"})
        try:
            with opener.open(operation, timeout=30) as response:
                contents = response.read(4 * 1024 * 1024 + 1)
                if len(contents) > 4 * 1024 * 1024:
                    raise ValueError("Canonical worker approval metadata is oversized")
                return contract.strict_json(contents)
        except urllib.error.HTTPError as error:
            raise ValueError(f"Canonical worker approval could not be read (GitHub HTTP {error.code})") from None

    explicit = os.environ.get("COCHEM_APPROVED_BASE_SHA", "")
    channel = os.environ.get("COCHEM_COURSE_CHANNEL", "")
    if explicit:
        if not contract.COMMIT_PATTERN.fullmatch(explicit):
            raise ValueError("The instructor's approved BASE Actions variable is invalid")
        allowed = {explicit}
        approval = "instructor-actions-variable"
    elif channel:
        if not channel.startswith(".cochem/course-channels/") or not channel.endswith(".json"):
            raise ValueError("The instructor's course channel must name canonical approval data")
        contract.safe_relative_path(channel)
        document = get("/contents/" + channel)
        if document.get("type") != "file" or document.get("encoding") != "base64":
            raise ValueError("The canonical approval channel is not a JSON data file")
        course_bytes = base64.b64decode(document["content"], validate=False)
        course = contract.strict_json(course_bytes)
        revision = course.get("approved_base_revision")
        if (course.get("schema_version") != "cochem.course-approval/1"
                or course.get("repository", canonical) != canonical
                or not isinstance(revision, str) or not contract.COMMIT_PATTERN.fullmatch(revision)):
            raise ValueError("The canonical course approval has no immutable BASE revision")
        allowed = {revision}
        approval = "instructor-course-channel"
    else:
        repository = get("")
        head = get("/commits/" + urllib.parse.quote(repository["default_branch"], safe=""))
        allowed = {head["sha"]}
        approval = "canonical-default-branch-or-stable-release"
        try:
            release = get("/releases/latest")
        except ValueError:
            release = None
        if release is not None and not release.get("draft") and not release.get("prerelease"):
            ref = get("/git/ref/tags/" + urllib.parse.quote(release["tag_name"], safe=""))["object"]
            for _ in range(4):
                if ref["type"] == "commit":
                    allowed.add(ref["sha"])
                    break
                if ref["type"] != "tag":
                    raise ValueError("The stable BASE release tag does not resolve to a commit")
                ref = get("/git/tags/" + ref["sha"])["object"]
    if request["worker_source_sha"] not in allowed:
        raise ValueError("The approved BASE worker changed or this revision is not authorized; refresh BASE and resubmit")
    actual = get("/commits/" + request["worker_source_sha"])
    if actual.get("sha") != request["worker_source_sha"]:
        raise ValueError("Canonical BASE did not verify the exact approved worker source")
    report = {"schema_version": "cochem.worker-approval/1", "canonical_repository": canonical,
              "worker_source_sha": request["worker_source_sha"], "assignment_source_sha": request["source_sha"],
              "approval": approval, "verified_at": datetime.now(timezone.utc).isoformat()}
    _atomic_json(output / "worker-approval.json", report)
    return report


def _preflight_periodic(calculation: dict) -> None:
    """Reject unsupported Product B operations before installing the free solver."""
    import math
    if (calculation.get("product_class") != "B" or calculation.get("method") != "PBE"
            or calculation.get("basis_set") not in {"PAW", "plane_wave"}
            or calculation.get("charge", 0) != 0 or calculation.get("multiplicity", 1) != 1
            or any(calculation.get(field) for field in ("is_opt", "is_freq", "is_vpt2", "recipe", "implicit_solvation",
                "frozen_monomer_indices", "hessian_file", "r2_reference_manifest", "t9_fallback", "theory_tier", "cbs_cardinal_pair", "grid_stage"))):
        raise ValueError("The connected QE worker supports neutral closed-shell Product B PBE PAW SCF only")
    periodic = calculation["periodic"]
    allowed = {"cell_angstrom", "pbc", "pseudopotentials", "ecutwfc_ry", "ecutrho_ry", "kpoints", "conv_thr_ry",
               "max_scf_steps", "structure_provenance"}
    if set(periodic) - allowed or periodic.get("pbc", [True] * 3) != [True, True, True]:
        raise ValueError("QE requires three periodic boundaries and typed plane-wave controls")
    limits = {"ecutwfc_ry": (45, 1000), "ecutrho_ry": (360, 10000), "conv_thr_ry": (1e-8, 1e-6)}
    for name, (default, ceiling) in limits.items():
        value = periodic.get(name, default)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= ceiling:
            raise ValueError("QE cutoff/convergence values must be finite and within the native adapter bounds")
    if periodic.get("ecutrho_ry", 360) < 4 * periodic.get("ecutwfc_ry", 45):
        raise ValueError("The PAW density cutoff must be at least four times its wavefunction cutoff")
    mesh = periodic.get("kpoints", [2, 2, 2])
    if (not isinstance(mesh, list) or len(mesh) != 3 or any(type(point) is not int or not 1 <= point <= 32 for point in mesh)
            or math.prod(mesh) > 4096):
        raise ValueError("QE requires a finite native-adapter reciprocal mesh")
    cycles = periodic.get("max_scf_steps", 100)
    if type(cycles) is not int or not 1 <= cycles <= 1000:
        raise ValueError("QE needs a finite SCF iteration limit")


def verify_worker_checkout(output: Path) -> dict:
    import subprocess
    request = contract.strict_json((output / "request.json").read_bytes())
    if hashlib.sha256(contract.canonical_json(request)).hexdigest() != os.environ["REQUEST_SHA256"]:
        raise ValueError("The approved student request changed before canonical worker checkout")
    contract.validate_request(request)
    source = Path(__file__).resolve().parents[1]
    actual = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    approval = contract.strict_json((output / "worker-approval.json").read_bytes())
    if actual != request["worker_source_sha"] or approval["worker_source_sha"] != actual:
        raise ValueError("The canonical worker checkout differs from the approved request")
    inputs = output / "inputs"
    inputs.mkdir(exist_ok=True)
    for name, item in request["files"].items():
        destination = inputs / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        data = base64.b64decode(item["content_base64"], validate=True)
        if destination.exists():
            if destination.is_symlink() or destination.read_bytes() != data:
                raise ValueError("The materialized inline source changed before worker execution")
        else:
            destination.write_bytes(data)
            destination.chmod(0o600)
    if request["calculation"] is not None:
        _atomic_json(inputs / "calculation.json", request["calculation"])
    if request["capability_probe"] is not None:
        engines, modules = [], []
    elif request["calculation"] is not None:
        calculation = request["calculation"]
        if calculation["engine"] in {"orca", "cfour"}:
            admissible = dict(calculation)
            # Portable advanced inputs are authenticated separately and rebound
            # to worker-owned paths before full scientific/model validation.
            if request["scientific_inputs"] is not None or request["t9_request"] is not None:
                if calculation["engine"] != "orca":
                    raise ValueError("Advanced reference/Hessian/recovery inputs require ORCA")
                if calculation.get("hessian_file") is not None or calculation.get("r2_reference_manifest") is not None or calculation.get("t9_fallback") is not None:
                    raise ValueError("Do not submit workstation paths or executable configuration")
                if admissible.get("initial_hessian") == "READ":
                    if not request["scientific_inputs"] or request["scientific_inputs"]["kind"] != "read_hessian":
                        raise ValueError("READ requires an authenticated geometry-bound Hessian bundle")
                    admissible["initial_hessian"] = "Lindh"
                if admissible.get("recipe") == "R2":
                    if not request["scientific_inputs"] or request["scientific_inputs"]["kind"] != "r2_reference":
                        raise ValueError("R2 requires authentic CCSD(T)/CBS monomer reference evidence")
                    if (str(calculation.get("method", "")).upper() != "WB97M-V"
                            or str(calculation.get("basis_set", "")).upper() != "DEF2-QZVPP"
                            or calculation.get("is_opt") is not True):
                        raise ValueError("The connected R2 protocol requires wB97M-V/def2-QZVPP frozen-monomer optimization")
                    admissible["recipe"] = None
            _local_contract("actions_jobs").preflight_configuration(admissible)
        elif calculation["engine"] == "xtb":
            if str(calculation.get("method", "")).upper() not in {"GFN2-XTB", "GFN-FF"}:
                raise ValueError("The hosted xTB adapter supports GFN2-xTB and GFN-FF")
            for field in ("hessian_file", "r2_reference_manifest", "t9_fallback", "periodic", "recipe"):
                if calculation.get(field) is not None:
                    raise ValueError(f"The self-contained xTB request cannot include {field}")
        elif calculation["engine"] == "qe":
            _preflight_periodic(calculation)
        elif calculation["engine"] == "pyscf":
            if any(calculation.get(field) is not None for field in ("periodic", "recipe", "hessian_file", "r2_reference_manifest", "t9_fallback")):
                raise ValueError("The self-contained PySCF request cannot include external executable/checkpoint paths")
            if (calculation.get("method", "").upper() not in {"HF", "RHF"}
                    or calculation.get("multiplicity", 1) != 1
                    or any(calculation.get(field) for field in ("is_opt", "is_freq", "is_vpt2", "implicit_solvation"))):
                raise ValueError("The native PySCF worker supports explicitly requested restricted-HF single-point energy/gradients")
        engines, modules = [calculation["engine"]], []
        if request["t9_request"] is not None:
            engines.append("pyscf")
    else:
        provider_contract = _local_contract("student_research")
        provider_contract.validate_provider_request(request["provider"], request["files"])
        provider_contract.validate_provider_resources(request["provider"], request["resources"])
        engines = provider_contract.required_provider_engines(request["provider"])
        modules = provider_contract.required_provider_modules(request["provider"])
    if any(engine not in {"orca", "cfour", "xtb", "pyscf", "crest", "qe"} for engine in engines):
        raise ValueError("A requested provider engine has no reviewed hosted installer")
    if any(module not in {"topos", "torq"} for module in modules):
        raise ValueError("A requested provider module has no reviewed student installation")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            for key, value in {"orca": str("orca" in engines).lower(), "cfour": str("cfour" in engines).lower(),
                               "pyscf": str("pyscf" in engines).lower(), "crest": str("crest" in engines).lower(),
                               "qe": str("qe" in engines).lower(),
                               "probe": str(request["capability_probe"] is not None).lower(),
                               "scientific_inputs": str(request["scientific_inputs"] is not None).lower(),
                               "data_inputs": str(request["data_inputs"] is not None).lower(),
                               "modules": " ".join(modules)}.items():
                stream.write(f"{key}={value}\n")
    module_manifest = source / "scripts/module-distribution.json"
    (output / "worker-module-distribution.json").write_bytes(module_manifest.read_bytes())
    report = {"worker_source_sha": actual, "module_manifest_sha256": hashlib.sha256(module_manifest.read_bytes()).hexdigest()}
    _atomic_json(output / "worker-source.json", report)
    return report


def _run_xtb(request: dict, output: Path, registry: Path) -> dict:
    from cochem_base.calc.calculation_service import CalculationMatrixConfig, parse_run_geometry, run_calculation
    from cochem_base.calc.xtb_execution import validate_xtb_config
    from cochem_base.interfaces.scientific_jobs import validate_job_configuration
    calculation = request["calculation"]
    config = CalculationMatrixConfig.model_validate(calculation, strict=True)
    elements, _ = parse_run_geometry(config.geometry)
    validate_xtb_config(config, elements)
    validate_job_configuration(config)
    resources = request["resources"]
    result = run_calculation(output / "inputs/calculation.json", scratch=output / "native-scratch",
                             output=output / "native", registry_path=registry,
                             threads=resources["cores"], maxcore_mb=resources["maxcore_mb"], device="cpu")
    if result.get("status") != "EXECUTION_VERIFIED":
        raise RuntimeError("xTB did not publish a verified scientific result")
    _retain_native_archive(contract.strict_json((output / "native/result.json").read_bytes()), output, registry)
    return result


def _retain_native_archive(accepted: dict, output: Path, registry: Path) -> None:
    """Retain the actual completed SWMR store and audited registry for students."""
    import shutil
    store = Path(accepted["telemetry_path"])
    if store.is_symlink() or not store.is_file():
        raise ValueError("Native scientific telemetry must be a real regular datastore")
    def digest(path: Path) -> str:
        with path.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    target = output / "complexes.h5"
    original_digest = digest(store)
    shutil.copy2(store, target)
    if digest(target) != original_digest or digest(store) != original_digest:
        raise ValueError("Native scientific telemetry changed during publication")
    shutil.copy2(registry, output / "stage0-registry.json")
    _atomic_json(output / "telemetry-publication.json", {"archive": "complexes.h5",
        "sha256": original_digest, "telemetry_job_id": accepted["telemetry_job_id"],
        "original_runner_store": str(store), "registry": "stage0-registry.json",
        "registry_sha256": hashlib.sha256(registry.read_bytes()).hexdigest()})


def capability_probe(output: Path) -> dict:
    verify_worker_checkout(output)
    request = contract.strict_json((output / "request.json").read_bytes())
    if request["capability_probe"] is None:
        raise ValueError("This request is not an optional-engine readiness check")
    from scripts.probe_student_engines import probe_engines
    identity = _identity(request)
    identity.update(status="completed", operation_performed=False, capability_probe_performed=True,
                    result=probe_engines(request["capability_probe"]["engines"]))
    _atomic_json(output / "student-result.json", identity)
    return identity


def _download_git_bundle(request: dict, descriptor: dict) -> bytes:
    """Read an exact sealed data blob; never check out or import its branch."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise ValueError("Assignment input retrieval requires the job's read-only repository identity")
    opener = urllib.request.build_opener(type("NoRedirect", (urllib.request.HTTPRedirectHandler,),
        {"redirect_request": lambda self, *args, **kwargs: None})())

    def get(path, maximum=4 * 1024 * 1024):
        operation = urllib.request.Request("https://api.github.com/repos/" + request["repository"] + path,
            headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "CoChem-BASE-scientific-inputs"})
        try:
            with opener.open(operation, timeout=60) as response:
                contents = response.read(maximum + 1)
        except urllib.error.HTTPError as error:
            raise ValueError(f"The sealed assignment input could not be read (GitHub HTTP {error.code})") from None
        if len(contents) > maximum:
            raise ValueError("Scientific input metadata exceeds its bounded size")
        return contract.strict_json(contents)

    commit = get("/git/commits/" + descriptor["commit_sha"])
    if (commit.get("sha") != descriptor["commit_sha"]
            or [parent.get("sha") for parent in commit.get("parents", [])] != [request["source_sha"]]):
        raise ValueError("The sealed input commit must descend directly from the exact assignment source")
    tree_sha = commit["tree"]["sha"]
    parts = descriptor["path"].split("/")
    for index, part in enumerate(parts):
        tree = get("/git/trees/" + tree_sha)
        matches = [entry for entry in tree["tree"] if entry["path"] == part]
        if len(matches) != 1:
            raise ValueError("The input commit does not contain the exact sealed bundle path")
        entry = matches[0]
        if index < len(parts) - 1:
            if entry["type"] != "tree" or entry["mode"] != "040000":
                raise ValueError("Scientific input paths cannot traverse Git links or special entries")
            tree_sha = entry["sha"]
        elif entry["type"] != "blob" or entry["mode"] != "100644" or entry["sha"] != descriptor["blob_sha"]:
            raise ValueError("The input commit's blob differs from the sealed request")
    blob = get("/git/blobs/" + descriptor["blob_sha"], maximum=90 * 1024 * 1024)
    if blob.get("encoding") != "base64" or blob.get("size") != descriptor["bundle_size_bytes"]:
        raise ValueError("The scientific input blob size or encoding is invalid")
    contents = base64.b64decode(blob["content"].replace("\n", ""), validate=True)
    if len(contents) != descriptor["bundle_size_bytes"] or hashlib.sha256(contents).hexdigest() != descriptor["bundle_sha256"]:
        raise ValueError("The downloaded scientific ZIP differs from the submitted bytes")
    return contents


def download_data_inputs(output: Path) -> dict:
    request = contract.strict_json((output / "request.json").read_bytes())
    contract.validate_request(request)
    descriptor = request["data_inputs"]
    if descriptor is None:
        raise ValueError("This request has no original ingestion bundle")
    from cochem_base.interfaces.student_data_inputs import extract_data_bundle
    receipt = extract_data_bundle(_download_git_bundle(request, descriptor), output / "data-inputs",
        request_id=request["request_id"], geometry_sha256=descriptor["geometry_sha256"], kind=descriptor["kind"])
    _atomic_json(output / "data-inputs.json", receipt)
    _bind_original_inputs(request, output)
    return receipt


def download_scientific_inputs(output: Path) -> dict:
    """Fetch only the sealed input blob; never execute a data-branch checkout."""
    request = contract.strict_json((output / "request.json").read_bytes())
    descriptor = request["scientific_inputs"]
    contract.validate_request(request)
    if descriptor is None:
        raise ValueError("This request has no scientific input bundle")
    contents = _download_git_bundle(request, descriptor)
    from cochem_base.interfaces.scientific_inputs import extract_bundle
    extracted = extract_bundle(contents, output / "scientific-inputs", request_id=request["request_id"],
                               geometry_sha256=descriptor["geometry_sha256"], kind=descriptor["kind"],
                               entrypoint=descriptor["entrypoint"])
    receipt = {"manifest": extracted["manifest"], "manifest_sha256": extracted["manifest_sha256"],
               "paths": {name: str(path) for name, path in extracted["paths"].items()},
               "entrypoint_path": str(extracted["entrypoint_path"]),
               "scientific_validation_performed": False}
    _atomic_json(output / "scientific-inputs.json", receipt)
    return receipt


def _bind_original_inputs(request: dict, output: Path) -> dict | None:
    """Compatibility wrapper for the shared installed BASE input-binding authority."""
    from cochem_base.interfaces.student_original_inputs import bind_original_inputs
    return bind_original_inputs(request, output)


def _run_free_native(request: dict, output: Path, registry: Path) -> dict:
    import math
    from cochem_base.calc.calculation_service import CalculationMatrixConfig, run_calculation
    from cochem_base.interfaces.scientific_jobs import validate_job_configuration, calculation_capability
    raw = _bind_original_inputs(request, output)
    contents = contract.canonical_json(raw)
    config = CalculationMatrixConfig.model_validate_json(contents, strict=True)
    validate_job_configuration(config)
    if calculation_capability(config).adapter_status != "connected":
        raise ValueError("This free-engine operation has no connected native acceptance adapter")
    path = output / "inputs/worker-calculation.json"
    _atomic_json(path, raw)
    result = run_calculation(path, scratch=output / "native-scratch", output=output / "native",
        registry_path=registry, threads=request["resources"]["cores"], maxcore_mb=request["resources"]["maxcore_mb"], device="cpu")
    if result.get("status") != "EXECUTION_VERIFIED":
        raise RuntimeError("The free native scientific operation did not complete")
    accepted = contract.strict_json((output / "native/result.json").read_bytes())
    if (not math.isfinite(accepted.get("energy_hartree", float("nan")))
            or accepted.get("scf_converged", accepted.get("converged")) is not True):
        raise RuntimeError("Native free-engine result lacks converged finite energy")
    from cochem_base.core_engine.scientific_telemetry import read_scientific_results
    telemetry = read_scientific_results(accepted["telemetry_job_id"], store_path=Path(accepted["telemetry_path"]))
    if (not len(telemetry["energy_hartree"]) or float(telemetry["energy_hartree"][-1]) != accepted["energy_hartree"]
            or telemetry["elements"] != accepted["elements"]
            or telemetry["coordinates_angstrom"][-1].tolist() != accepted["coordinates_angstrom"]):
        raise RuntimeError("Native free-engine HDF5 evidence contradicts its published result")
    _retain_native_archive(accepted, output, registry)
    return result


def _run_advanced_orca(request: dict, output: Path, registry: Path) -> dict:
    import math
    from cochem_base.calc.calculation_service import CalculationMatrixConfig, run_calculation
    from cochem_base.interfaces.scientific_jobs import validate_job_configuration, calculation_capability
    from cochem_base.core_engine.execution_authority import authorize_engine_execution
    raw = dict(request["calculation"])
    if request["scientific_inputs"] is not None:
        intake = contract.strict_json((output / "scientific-inputs.json").read_bytes())
        entrypoint = Path(intake["entrypoint_path"])
        if request["scientific_inputs"]["kind"] == "r2_reference":
            raw["r2_reference_manifest"] = str(entrypoint)
        else:
            # The canonical native runner performs geometry binding and tensor
            # transformation for every environment, retaining the original file.
            raw["hessian_file"] = str(entrypoint)
    if request["t9_request"] is not None:
        recovery = dict(request["t9_request"])
        authority = authorize_engine_execution("pyscf", registry_path=registry,
            cores=recovery["threads"],
            maxcore_mb=math.ceil(recovery["memory_mb"] / recovery["threads"]))
        recovery["python_executable"] = authority.executable
        raw["t9_fallback"] = recovery
    contents = contract.canonical_json(raw)
    config = CalculationMatrixConfig.model_validate_json(contents, strict=True)
    validate_job_configuration(config)
    if calculation_capability(config).adapter_status != "connected":
        raise ValueError("The requested advanced operation has no connected scientific acceptance adapter")
    normalized = output / "inputs/worker-calculation.json"
    _atomic_json(normalized, raw)
    result = run_calculation(normalized, scratch=output / "native-scratch", output=output / "native",
                             registry_path=registry, threads=request["resources"]["cores"],
                             maxcore_mb=request["resources"]["maxcore_mb"], device="cpu")
    if result.get("status") not in {"EXECUTION_VERIFIED", "T9_FALLBACK_VERIFIED"}:
        raise RuntimeError("The advanced native scientific operation did not complete")
    if result["status"] == "EXECUTION_VERIFIED":
        accepted = contract.strict_json((output / "native/result.json").read_bytes())
        if (accepted.get("engine") != "orca" or accepted.get("converged") is not True
                or not math.isfinite(accepted["energy_hartree"])):
            raise RuntimeError("The advanced native result is not a converged finite energy")
        from cochem_base.core_engine.scientific_telemetry import read_scientific_results
        telemetry = read_scientific_results(accepted["telemetry_job_id"], store_path=Path(accepted["telemetry_path"]))
        if (not len(telemetry["energy_hartree"])
                or float(telemetry["energy_hartree"][-1]) != accepted["energy_hartree"]
                or telemetry["elements"] != accepted["elements"]
                or telemetry["coordinates_angstrom"][-1].tolist() != accepted["coordinates_angstrom"]):
            raise RuntimeError("Advanced native scientific archive differs from its published result")
        _retain_native_archive(accepted, output, registry)
    else:
        if result.get("original_single_reference_rejected") is not True:
            raise RuntimeError("The alternative T9 method lacks explicit rejection of its original single-reference result")
        fallback = result["fallback"]
        from cochem_base.core_engine.scientific_telemetry import read_scientific_results
        telemetry = read_scientific_results(fallback["telemetry_job_id"], store_path=Path(fallback["telemetry_path"]))
        if (not len(telemetry["energy_hartree"])
                or float(telemetry["energy_hartree"][-1]) != fallback["energy_hartree"]
                or telemetry["nuclides"] != fallback["nuclides"]
                or telemetry["metadata"][-1].get("tier") != "T9"):
            raise RuntimeError("The alternative T9 result contradicts its native scientific archive")
        _retain_native_archive(fallback, output, registry)
    return result


def execute(output: Path, registry: Path, module_root: Path | None = None) -> dict:
    verify_worker_checkout(output)
    request = contract.strict_json((output / "request.json").read_bytes())
    contract.validate_request(request)
    if hashlib.sha256(contract.canonical_json(request)).hexdigest() != os.environ["REQUEST_SHA256"]:
        raise ValueError("The materialized student request changed before execution")
    identity = _identity(request)
    try:
        if request["calculation"] is not None:
            engine = request["calculation"]["engine"]
            _bind_original_inputs(request, output)
            if engine == "orca" and (request["scientific_inputs"] is not None or request["t9_request"] is not None):
                result = _run_advanced_orca(request, output, registry)
            elif engine in {"orca", "cfour"}:
                from scripts.run_actions_calculation import run_job
                result = run_job(output / "inputs", "calculation.json", registry=registry,
                                 output=output / "native", engine=engine, **request["resources"])
            elif engine == "xtb":
                result = _run_xtb(request, output, registry)
            else:
                result = _run_free_native(request, output, registry)
        else:
            _bind_original_inputs(request, output)
            from cochem_base.interfaces.student_research import execute_provider_request
            result = execute_provider_request(request["provider"], output / "inputs", output / "provider",
                                              root=module_root, registry=registry,
                                              resources={**request["resources"], "threads": request["resources"]["cores"],
                                                         "memory_mb": request["resources"]["cores"] * request["resources"]["maxcore_mb"],
                                                         "budget_seconds": 1800})
            if (result.get("status") != "completed" or result.get("operation_performed") is not True):
                raise RuntimeError("The requested provider operation did not complete")
        identity.update(status="completed", operation_performed=True, result=result)
        return identity
    except Exception as error:
        identity.update(status="failed", operation_performed=False, error_type=type(error).__name__,
                        error=str(error))
        raise
    finally:
        _atomic_json(output / "student-result.json", identity)


def finalize(output: Path) -> dict:
    """Seal artifacts only; never collect a licensed runtime or module environment."""
    report_path = output / "student-result.json"
    if not report_path.exists():
        return {"status": "no_valid_request"}
    report = contract.strict_json(report_path.read_bytes())
    if report.get("status") == "prepared":
        report.update(status="failed", operation_performed=False,
                      error="Provisioning or setup did not complete; no scientific result is claimed")
        _atomic_json(report_path, report)
    for engine in ("orca", "cfour"):
        if os.environ.get(f"COCHEM_{engine.upper()}_REQUESTED") != "true":
            continue
        outcome = os.environ.get(f"COCHEM_{engine.upper()}_PROVISIONING_OUTCOME")
        if outcome == "failure":
            report.setdefault("engine_availability", {})[engine] = {
                "status": "unavailable", "provisionable": False, "installed_for_run": False,
                "reason": f"Actual {engine.upper()} provisioning failed in this calculation job. Recheck instructor asset access before retrying."}
            report["failure_category"] = "engine_provisioning"
            _atomic_json(report_path, report)
    _retain_crash_records(output)
    files = {}
    total = 0
    for path in sorted(output.rglob("*")):
        if path.is_symlink():
            path.unlink()
            continue
        if not path.is_file() or path.name == "publication-manifest.json":
            continue
        if path.name.upper() in {"GENBAS", "ECPDATA"} or any(part in {"native-scratch", "CrashRecords"} for part in path.relative_to(output).parts):
            path.unlink()
            continue
        with path.open("rb") as stream:
            prefix = stream.read(4)
            if prefix == b"\x7fELF" or prefix[:2] == b"MZ":
                raise ValueError("A runtime executable was found in the scientific evidence; publication refused")
            stream.seek(0)
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        total += path.stat().st_size
        if total > 100 * 1024 * 1024 or len(files) >= 4000:
            raise ValueError("Scientific evidence exceeds the bounded student artifact limit")
        files[path.relative_to(output).as_posix()] = {"sha256": digest, "size_bytes": path.stat().st_size}
    identity = {key: report[key] for key in ("request_id", "repository", "source_sha", "worker_source_sha", "payload_sha256", "run_id", "run_attempt")}
    manifest = {"schema_version": "cochem.student-publication/1", **identity, "files": files}
    _atomic_json(output / "publication-manifest.json", manifest)
    return manifest


def _retain_crash_records(output: Path) -> None:
    """Copy authentic immutable diagnostic JSON before scratch deletion."""
    retained = output / "crash-provenance"
    records = {}
    for source in output.rglob("crash-*.json"):
        if "CrashRecords" not in source.relative_to(output).parts:
            continue
        if source.is_symlink() or not source.is_file() or source.stat().st_size > 1024 * 1024:
            raise ValueError("Crash provenance must be a bounded regular immutable JSON record")
        contents = source.read_bytes()
        record = contract.strict_json(contents)
        digest = record.pop("sha256", None)
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if (record.get("event") != "process_crash" or record.get("@type") != "Event"
                or digest != hashlib.sha256(canonical).hexdigest()):
            raise ValueError("Immutable crash provenance does not match its own recorded SHA-256")
        name = "crash-" + hashlib.sha256(contents).hexdigest() + ".json"
        if name not in records:
            retained.mkdir(exist_ok=True)
            destination = retained / name
            if destination.exists():
                if destination.is_symlink() or destination.read_bytes() != contents:
                    raise ValueError("Retained immutable crash provenance differs from its original record")
            else:
                with destination.open("xb") as stream:
                    stream.write(contents)
            destination.chmod(0o444)
            records[name] = {"source_path": str(source), "record_sha256": digest,
                             "file_sha256": hashlib.sha256(contents).hexdigest()}
    if records:
        _atomic_json(output / "crash-provenance-receipt.json", {"records": records,
            "scientific_execution_claimed_from_crash": False, "licensed_input_dependencies": "hash_only"})


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if callable(getattr(stream, "reconfigure", None)):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--module-root", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--preflight-only", action="store_true")
    modes.add_argument("--finalize-only", action="store_true")
    modes.add_argument("--approve-worker-only", action="store_true")
    modes.add_argument("--verify-worker-only", action="store_true")
    modes.add_argument("--capability-probe", action="store_true")
    modes.add_argument("--download-scientific-inputs", action="store_true")
    modes.add_argument("--download-data-inputs", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.preflight_only:
            preflight(args.output)
            print("Hash-bound student request and hosted limits verified.")
        elif args.finalize_only:
            finalize(args.output)
        elif args.approve_worker_only:
            approve_worker(args.output)
        elif args.verify_worker_only:
            verify_worker_checkout(args.output)
        elif args.capability_probe:
            capability_probe(args.output)
        elif args.download_scientific_inputs:
            download_scientific_inputs(args.output)
        elif args.download_data_inputs:
            download_data_inputs(args.output)
        else:
            if args.registry is None:
                parser.error("Execution requires the fresh Stage 0 registry")
            execute(args.output, args.registry, args.module_root)
    except Exception as error:
        # Source/binary credentials are absent from the execution environment.
        print(f"Student operation failed: {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
