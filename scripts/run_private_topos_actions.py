"""Consume the exact private TOPOS kit, provisioner receipts and typed request.

This worker never downloads from the laboratory. Its owning repository token
reads its own task releases, and BASE retains scientific execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from cochem_base.interfaces.private_topos_actions import (
    MAX_KIT_BYTES,
    WORKFLOW,
    load_bundle,
    verify_kit_release,
)


def worker_bundle(checkout: Path) -> dict:
    from cochem_base.interfaces.private_actions import run_belongs_to_task
    from scripts.private_engine_assets import _api, _personal_private
    from scripts.private_topos_job import validate_bound_request

    bundle = load_bundle(os.environ.get("TOPOS_STAGING_BUNDLE", "").encode(),
                         os.environ.get("TOPOS_STAGING_BUNDLE_SHA256", ""))
    if (os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("TOPOS_DISPATCH_ID") != bundle["task_id"]
            or any(os.environ.get(key) != value for key, value in (
                ("GITHUB_REPOSITORY", bundle["repository"]), ("GITHUB_REPOSITORY_ID", str(bundle["repository_id"])),
                ("GITHUB_REPOSITORY_OWNER_ID", str(bundle["owner_id"])), ("GITHUB_SHA", bundle["source_sha"]),
                ("GITHUB_REF", bundle["ref"]),
                ("GITHUB_WORKFLOW_REF", f"{bundle['repository']}/{WORKFLOW}@{bundle['ref']}")))):
        raise ValueError("The TOPOS worker differs from its exact owning project/workflow/source/task")
    observed = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True, timeout=10, check=False)
    dirty = subprocess.run(["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=all"],
        capture_output=True, timeout=10, check=False)
    if observed.returncode or dirty.returncode or observed.stdout.decode().strip() != bundle["source_sha"] or dirty.stdout:
        raise ValueError("The actual checkout must retain the exact clean staged Git source")
    actual = _personal_private(bundle["repository"], owner=False)
    if actual["id"] != bundle["repository_id"] or actual["owner"]["id"] != bundle["owner_id"]:
        raise ValueError("The live personal private project differs from TOPOS staging")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"[1-9][0-9]*", run_id):
        raise ValueError("The actual owning-project run ID is required")
    run = _api(f"repos/{bundle['repository']}/actions/runs/{run_id}")
    identity = {"task_id": bundle["task_id"],
        "destination": {"repository_id": bundle["repository_id"]},
        "project": {"source_sha": bundle["source_sha"], "ref": bundle["ref"], "workflow_path": WORKFLOW}}
    if (run.get("id") != int(run_id) or run.get("status") != "in_progress"
            or run.get("run_attempt") != int(os.environ.get("GITHUB_RUN_ATTEMPT", "0"))
            or not run_belongs_to_task(run, identity, bundle["repository"])):
        raise ValueError("The actual Actions run does not belong to this TOPOS task/source")
    title_tasks = re.findall(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])", run.get("display_title", ""))
    if any(item["task_id"] not in title_tasks for item in bundle["engines"].values()):
        raise ValueError("The owned run must correlate every separate engine staging task")
    if (os.environ.get("JOB_FILE") != bundle["intent"]["job_file"]
            or os.environ.get("TOPOS_REQUEST_SHA256") != bundle["intent"]["input_sha256"]):
        raise ValueError("The dispatch selected a different TOPOS request file/checksum")
    # Derive resource variables from the immutable staging intent, never form defaults.
    environment = {**os.environ, "JOB_CORES": str(bundle["intent"]["cores"]),
                   "JOB_MAXCORE_MB": str(bundle["intent"]["maxcore_mb"])}
    validate_bound_request(checkout, bundle["intent"], environment)
    verify_kit_release(bundle)
    return bundle


def preflight(checkout: Path, output: Path) -> None:
    from scripts.private_engine_assets import _private_output

    bundle = worker_bundle(checkout)
    values = {"JOB_CORES": str(bundle["intent"]["cores"]), "JOB_MAXCORE_MB": str(bundle["intent"]["maxcore_mb"]),
              "TOPOS_REQUIRES_ORCA": str("orca" in bundle["engines"]).lower(),
              "TOPOS_REQUIRES_CFOUR": str("cfour" in bundle["engines"]).lower()}
    for engine, item in bundle["engines"].items():
        values.update({engine + "_receipt": json.dumps(item["receipt"], sort_keys=True, separators=(",", ":"), ensure_ascii=False),
                       engine + "_sha256": item["sha256"], engine + "_task": item["task_id"]})
    output = _private_output(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("Retain a new external preflight proof")
    output.write_text(json.dumps({"schema_version": "cochem.private-topos-preflight/1", "task_id": bundle["task_id"],
        "source_sha": bundle["source_sha"], "intent": bundle["intent"], "required_engines": bundle["required_engines"],
        "scientific_execution_performed": False}, indent=2) + "\n")
    for target in ("GITHUB_ENV", "GITHUB_OUTPUT"):
        with Path(os.environ[target]).open("a", encoding="utf-8") as stream:
            for name, value in values.items():
                if any(char in value for char in "\r\n\x00"):
                    raise ValueError("Invalid multiline worker control")
                # Receipts belong to step outputs, not persistent process environment.
                if target == "GITHUB_OUTPUT" or name.isupper():
                    stream.write(name + "=" + value + "\n")


def download_kit(checkout: Path, output: Path) -> None:
    from scripts.hosted_module_kit import verify_extracted_archive
    from scripts.private_engine_assets import _download, _private_output

    bundle = worker_bundle(checkout)
    output = _private_output(output)
    output.mkdir(parents=True, exist_ok=False)
    archive = output.parent / "mandatory-kit.zip"
    _download(bundle["repository"], bundle["kit"], archive)
    total = 0
    names = set()
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            path = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            total += member.file_size
            if (not member.filename or path.is_absolute() or ".." in path.parts or "\\" in member.filename
                    or path.as_posix() != member.filename or member.filename in names
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG) or member.is_dir()
                    or total > MAX_KIT_BYTES):
                raise ValueError("The privately staged kit contains unsafe or oversized members")
            names.add(member.filename)
            destination = output.joinpath(*path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(member) as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target)
    verify_extracted_archive(archive, output, bundle["intent"]["kit_sha256"])


def run_request(checkout: Path, kit: Path, modules: Path, output: Path) -> dict:
    from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
    from cochem_base.interfaces.module_execution import execute_module_handoff
    from scripts.manage_modules import install_module, load_manifest, verify_installation
    from scripts.mandatory_ecosystem import _setup_environment, inspect_kit
    from scripts.module_request import handoff_options, read_topos_request
    from scripts.private_engine_assets import _private_output

    bundle = worker_bundle(checkout)
    output, modules = _private_output(output), _private_output(modules)
    output.mkdir(parents=True, exist_ok=False)
    committed_path = checkout / bundle["intent"]["job_file"]
    committed_bytes = committed_path.read_bytes()
    if hashlib.sha256(committed_bytes).hexdigest() != bundle["intent"]["input_sha256"]:
        raise ValueError("The committed request changed before its frozen private snapshot")
    request_path = output / "submitted-job.json"
    request_path.write_bytes(committed_bytes)
    request = read_topos_request(request_path)
    spec = load_manifest()["modules"]["topos"]
    inspected = inspect_kit(kit, spec)
    if inspected["pins"] != bundle["intent"]["source_pins"]:
        raise ValueError("The reviewed kit source identities differ from the actual staged request")
    install_module("topos", spec, modules, ecosystem_kit=kit)
    from cochem_base.interfaces.private_topos_actions import _PROBE
    installed = verify_installation("topos", spec, modules)
    selected = subprocess.run([installed["python_path"], "-I", "-B", "-c", _PROBE],
        input=request_path.read_bytes(), env=_setup_environment(), cwd=modules,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    if selected.returncode:
        raise ValueError("The installed typed recipe or pinned native parser dependencies failed preflight")
    classified = json.loads(selected.stdout)
    if classified["native_engines"] != bundle["required_engines"]:
        raise ValueError("The installed source-selected recipe differs from the exact staged native engine requirements")
    molecule = request["molecule"]
    # Retain exactly the committed request; XYZ is a declared transport projection.
    xyz = output / "starting-geometry.xyz"
    xyz.write_text(str(len(molecule["symbols"])) + "\nTOPOS declared atom order; full request retained\n" +
        "".join(symbol + " " + " ".join(format(float(value), ".17g") for value in row) + "\n"
                for symbol, row in zip(molecule["symbols"], molecule["coordinates"], strict=True)))
    operation, options = handoff_options("topos", request_path)
    prepare_module_handoff("topos", xyz, output / "handoff", operation=operation, options=options)
    hosted_budget = None
    if request["include_queue_in_budget"]:
        from cochem_base.interfaces.private_actions import _canonical, run_belongs_to_task
        from scripts.private_engine_assets import _api
        from scripts.private_topos_job import load_hosted_budget
        actual = _api(f"repos/{bundle['repository']}/actions/runs/{os.environ['GITHUB_RUN_ID']}")
        identity = {"task_id": bundle["task_id"], "destination": {"repository_id": bundle["repository_id"]},
            "project": {"source_sha": bundle["source_sha"], "ref": bundle["ref"], "workflow_path": WORKFLOW}}
        if (not run_belongs_to_task(actual, identity, bundle["repository"])
                or actual.get("status") != "in_progress" or actual.get("run_attempt") != int(os.environ["GITHUB_RUN_ATTEMPT"])):
            raise ValueError("The authenticated queue origin differs from the exact executing run")
        control = {"schema_version": "cochem.topos-hosted-budget/1",
            "request_sha256": hashlib.sha256(_canonical(request)).hexdigest(),
            "repository": bundle["repository"], "repository_id": bundle["repository_id"], "owner_id": bundle["owner_id"],
            "source_sha": bundle["source_sha"], "ref": bundle["ref"], "workflow_path": WORKFLOW,
            "run_id": actual["id"], "run_attempt": actual["run_attempt"], "workflow_created_at": actual["created_at"]}
        hosted_budget = output / "hosted-budget-controls.json"
        hosted_budget.write_bytes(_canonical(control))
        load_hosted_budget(hosted_budget, request, os.environ)
    execution = execute_module_handoff(output / "handoff/handoff.json", output / "execution",
        root=modules, timeout=bundle["intent"]["receiver_timeout"], hosted_budget=hosted_budget)
    status = 0 if execution.get("status") == "completed" else 1
    result = {"schema_version": "cochem.private-topos-calculation/1", "task_id": bundle["task_id"],
              "source_sha": bundle["source_sha"], "input_sha256": bundle["intent"]["input_sha256"],
              "source_pins": bundle["intent"]["source_pins"], "receiver_exit_code": status,
              "cfour_parser_versions": classified["cfour_parser_versions"],
              "github_run_id": os.environ["GITHUB_RUN_ID"], "github_run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
              "published": False, "scientific_qualification_inferred": False}
    (output / "worker-receipt.json").write_text(json.dumps(result, indent=2) + "\n")
    if hashlib.sha256((output / "submitted-job.json").read_bytes()).hexdigest() != bundle["intent"]["input_sha256"]:
        raise ValueError("The actual scientific request changed during execution")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("preflight", "download-kit", "run"))
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--kit", type=Path)
    parser.add_argument("--modules", type=Path)
    args = parser.parse_args(argv)
    if args.mode == "preflight":
        preflight(args.checkout, args.output)
    elif args.mode == "download-kit":
        download_kit(args.checkout, args.output)
    else:
        if args.kit is None or args.modules is None:
            parser.error("run requires the actual downloaded --kit and external --modules storage")
        result = run_request(args.checkout, args.kit, args.modules, args.output)
        return int(result["receiver_exit_code"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
