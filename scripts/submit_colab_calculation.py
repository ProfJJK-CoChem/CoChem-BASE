"""Student CLI entrypoint for submitting and polling Google Colab GPU calculations.

Uses the scoped `COLAB_OFFLOAD_DISPATCH_TOKEN` secret (bound via `COCHEM_COLAB_ACCESS_SECRET`
in the student's enrolled repository) to HMAC-sign a data-only calculation request
and submit it to the instructor's controller repository (`ProfJJK-CoChem/CoChem-Project-Access`),
which dispatches the calculation to a Google Colab GPU (`w53`..`w58`) and enforces the
dynamic monthly per-student CU quota (`1,750.0 / N_students` CUs per calendar month)
without ever exposing the instructor's Google Colab OAuth token (`token.json`).
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

def _local_colab_contract():
    root = Path(__file__).resolve().parents[1]
    # Checkout and installed-wheel layouts, bound to this CLI's own location.
    candidates = [path.resolve() for path in (
        root / "src/cochem_base/interfaces/student_colab.py",
        root / "cochem_base/interfaces/student_colab.py",
    ) if path.is_file()]
    if len(candidates) != 1:
        raise ImportError("Exactly one Colab contract beside this CLI is required")
    path = candidates[0]
    key = "_cochem_colab_source_" + hashlib.sha256(str(path).encode()).hexdigest()
    cached = sys.modules.get(key)
    if cached is not None:
        if Path(cached.__file__).resolve() != path:
            raise ImportError("The Colab CLI contract cache belongs to another source")
        return cached
    spec = importlib.util.spec_from_file_location(key, path)
    if spec is None or spec.loader is None:
        raise ImportError("The reviewed Colab contract is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[key] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(key, None)
        raise
    return module


contract = _local_colab_contract()
CourseAccessError = contract.CourseAccessError
GitHubAPI = contract.GitHubAPI
repository_name = contract.repository_name
SCHEMA_RESULT = contract.SCHEMA_RESULT
package_student_colab_request = contract.package_student_colab_request
submit_student_colab_issue = contract.submit_student_colab_issue


def _github_token() -> str:
    token = (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
    if not token:
        raise CourseAccessError(
            "GH_TOKEN or GITHUB_TOKEN is required to submit a Google Colab GPU request to the controller queue."
        )
    return token


def poll_colab_issue_result(
    api: GitHubAPI,
    controller_repository: str,
    issue_number: int,
    *,
    timeout_seconds: int = 1800,
    poll_interval_seconds: int = 15,
) -> dict[str, Any]:
    """Poll the controller issue until the workstation AutoSweeper posts `cochem.student-colab-result.v1`."""
    ctrl = repository_name(controller_repository)
    owner, repo = ctrl.split("/", 1)
    deadline = time.monotonic() + max(timeout_seconds, 1)
    while True:
        comments = api.request_json("GET", f"/repos/{owner}/{repo}/issues/{int(issue_number)}/comments?per_page=100")
        if isinstance(comments, list):
            for comment in reversed(comments):
                body = str((comment or {}).get("body") or "")
                if SCHEMA_RESULT in body:
                    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", body, flags=re.DOTALL)
                    if fence:
                        data = json.loads(fence.group(1))
                        if isinstance(data, dict) and data.get("schema") == SCHEMA_RESULT:
                            return data
                if "Refused Colab GPU request:" in body or "Google Colab GPU request error:" in body:
                    raise CourseAccessError(body.strip())
        if time.monotonic() >= deadline:
            return {
                "schema": SCHEMA_RESULT,
                "status": "pending",
                "issue_number": int(issue_number),
                "controller_repository": ctrl,
            }
        time.sleep(max(poll_interval_seconds, 5))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--student-id", default=os.environ.get("GITHUB_USER") or os.environ.get("GITHUB_ACTOR") or "")
    parser.add_argument("--job-id", required=True, help="Unique job identifier (e.g., orgo1-formaldehyde-freq)")
    parser.add_argument("--engine", default="ORCA", choices=("ORCA", "CFOUR", "XTB", "PYSCF"))
    parser.add_argument("--method", default="r2SCAN-3c")
    parser.add_argument("--basis-set", default=None)
    parser.add_argument("--xyz-file", type=Path, help="Path to XYZ coordinate file")
    parser.add_argument("--xyz", default="", help="Inline XYZ coordinate string")
    parser.add_argument("--charge", type=int, default=0)
    parser.add_argument("--multiplicity", type=int, default=1)
    parser.add_argument("--no-opt", action="store_true")
    parser.add_argument("--no-freq", action="store_true")
    parser.add_argument("--estimated-cu", type=float, default=2.5)
    parser.add_argument(
        "--controller-repository",
        default=os.environ.get("COCHEM_ACCESS_CONTROLLER_REPOSITORY", "ProfJJK-CoChem/CoChem-Project-Access"),
    )
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--wait", action="store_true", help="Wait and poll for the completed Colab GPU result")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args(argv)

    xyz_text = args.xyz.strip()
    if args.xyz_file is not None:
        xyz_text = args.xyz_file.read_text(encoding="utf-8").strip()

    packaged = package_student_colab_request(
        student_id=args.student_id,
        job_id=args.job_id,
        engine=args.engine,
        method=args.method,
        basis_set=args.basis_set,
        geometry_xyz=xyz_text,
        repository=args.repository or None,
        estimated_cu=args.estimated_cu,
        charge=args.charge,
        multiplicity=args.multiplicity,
        is_opt=not args.no_opt,
        is_freq=not args.no_freq,
    )
    api = GitHubAPI(_github_token())
    submitted = submit_student_colab_issue(api, args.controller_repository, packaged)
    if args.wait:
        result = poll_colab_issue_result(
            api,
            args.controller_repository,
            submitted["issue_number"],
            timeout_seconds=args.timeout_seconds,
        )
        submitted["result"] = result
    print(json.dumps(submitted, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
