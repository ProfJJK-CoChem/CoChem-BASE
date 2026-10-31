"""Report nonsecret project settings from an Actions job, without running science.

The workflow converts credential presence to booleans before invoking this
script. No credential value or credential label belongs in this report.
The calculation worker independently revalidates software authorization.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import sys
import json
import os
import re
import uuid
from pathlib import Path


def _research_admission(source: Path) -> dict:
    path = source / "src/cochem_base/interfaces/student_actions_admission.py"
    spec = importlib.util.spec_from_file_location("cochem_setup_admission", path)
    if spec is None or spec.loader is None:
        raise ValueError("The reviewed research admission contract is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    raw = (source / module.DESCRIPTOR_PATH).read_bytes()
    descriptor = module.parse_descriptor(raw)
    for relative, expected in descriptor["required_files"].items():
        if hashlib.sha256((source / relative).read_bytes()).hexdigest() != expected:
            raise ValueError("The project research admission files need an instructor update")
    return {"protocol": module.PROTOCOL, "ledger_ref": module.LEDGER_REF,
            "descriptor_sha256": hashlib.sha256(raw).hexdigest()}


def project_setup_report(environment: dict[str, str], *, source: Path | None = None) -> dict:
    request_id = environment.get("SETUP_REQUEST_ID", "")
    if str(uuid.UUID(request_id)) != request_id:
        raise ValueError("The setup check needs its original request identifier.")
    repository = environment.get("GITHUB_REPOSITORY", "")
    source_sha = environment.get("GITHUB_SHA", "")
    revision = environment.get("COCHEM_APPROVED_BASE_SHA", "")
    channel = environment.get("COCHEM_COURSE_CHANNEL", "")
    if (not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository)
            or not re.fullmatch(r"[a-f0-9]{40}", source_sha)
            or environment.get("GITHUB_EVENT_NAME") != "workflow_dispatch"
            or not environment.get("DEFAULT_BRANCH")
            or environment.get("GITHUB_REF") != "refs/heads/" + environment["DEFAULT_BRANCH"]):
        raise ValueError("The setup check must run on this project's default branch.")
    if revision and not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Ask the instructor to correct the project's selected BASE version.")
    if channel and not re.fullmatch(r"\.cochem/course-channels/[a-z0-9][a-z0-9_-]*\.json", channel):
        raise ValueError("Ask the instructor to correct the project's BASE update settings.")
    run_id = int(environment.get("GITHUB_RUN_ID", "0"))
    run_attempt = int(environment.get("GITHUB_RUN_ATTEMPT", "0"))
    if run_id < 1 or run_attempt < 1:
        raise ValueError("The setup check has no valid GitHub run identity.")
    access = {}
    for kind in ("source", "orca", "cfour"):
        value = environment.get("COCHEM_" + kind.upper() + "_AVAILABLE", "")
        if value not in {"true", "false"}:
            raise ValueError("The setup check needs a yes/no access status for each optional component.")
        access[kind] = value == "true"
    return {"schema_version": "cochem.project-setup/2",
            "research_admission": _research_admission(source or Path(__file__).resolve().parents[1]), "request_id": request_id,
            "repository": repository, "source_sha": source_sha,
            "run_id": run_id, "run_attempt": run_attempt,
            "approved_base_sha": revision, "course_channel": channel, "access": access}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = project_setup_report(dict(os.environ))
    except (ValueError, TypeError):
        parser.exit(1, "The project setup settings are invalid. Ask the instructor to check the selected BASE version and access configuration.\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
