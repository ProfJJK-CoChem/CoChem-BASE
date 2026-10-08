"""Instructor-only GitHub Actions entry point for private project enrollment."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

# Import the exact controller-owned module without importing the chemistry
# interfaces package. The controller needs only cryptography and libsodium;
# neither a quantum engine nor the full GUI runtime belongs in this job.
_module_path = Path(__file__).resolve().parents[1] / "src/cochem_base/interfaces/course_access.py"
_spec = importlib.util.spec_from_file_location("_cochem_course_access_controller", _module_path)
if _spec is None or _spec.loader is None:
    raise SystemExit("The reviewed instructor controller module is missing.")
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)
ControllerConfig = _module.ControllerConfig
CourseAccessError = _module.CourseAccessError
EnrollmentRequest = _module.EnrollmentRequest
GitHubAPI = _module.GitHubAPI
parse_enrollment = _module.parse_enrollment
provision_project = _module.provision_project
repository_name = _module.repository_name


def validate_event(event: dict, environment: dict[str, str], config: ControllerConfig,
                   controller_api: GitHubAPI) -> tuple[EnrollmentRequest, str, int | None]:
    """The GitHub event is data; only the configured private controller may run."""
    repository = event.get("repository", {})
    if not isinstance(repository, dict):
        raise CourseAccessError("The trusted controller repository metadata is invalid.")
    default_branch = repository.get("default_branch")
    if (not isinstance(repository, dict) or repository.get("private") is not True
            or str(repository.get("full_name", "")).lower() != config.repository.lower()
            or environment.get("GITHUB_REPOSITORY", "").lower() != config.repository.lower()
            or repository.get("owner", {}).get("type") != "Organization"
            or not isinstance(default_branch, str)
            or environment.get("GITHUB_REF") != "refs/heads/" + default_branch):
        raise CourseAccessError("Run enrollment only from the configured private instructor controller's default branch.")
    commit = controller_api.call("GET", f"/repos/{config.repository}/commits/{default_branch}")
    if (not isinstance(commit, dict) or commit.get("sha") != environment.get("GITHUB_SHA")
            or not re.fullmatch(r"[a-f0-9]{40}", str(commit.get("sha", "")))):
        raise CourseAccessError("The controller source is no longer its trusted default-branch revision; rerun enrollment.")
    kind = environment.get("GITHUB_EVENT_NAME")
    if kind == "issues":
        issue = event.get("issue", {})
        if (event.get("action") not in {"opened", "reopened", "edited"}
                or not isinstance(issue, dict) or "pull_request" in issue
                or type(issue.get("number")) is not int or issue["number"] <= 0):
            raise CourseAccessError("Only a data-only enrollment issue is supported.")
        author = issue.get("user", {}).get("login")
        if not isinstance(author, str):
            raise CourseAccessError("The enrollment issue has no valid student author.")
        enrollment = parse_enrollment(issue.get("body", ""))
        return enrollment, author, issue["number"]
    if kind == "workflow_dispatch":
        actor = environment.get("GITHUB_ACTOR", "")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", actor):
            raise CourseAccessError("The instructor maintenance actor is invalid.")
        permission = controller_api.call("GET", f"/repos/{config.repository}/collaborators/{actor}/permission")
        if not isinstance(permission, dict) or permission.get("permission") not in {"admin", "write", "maintain"}:
            raise CourseAccessError("Only an instructor with controller write access may maintain project credentials.")
        inputs = event.get("inputs", {})
        if not isinstance(inputs, dict):
            raise CourseAccessError("The maintenance request is invalid.")
        target = repository_name(inputs.get("project_repository", ""))
        engines = inputs.get("engines", "orca cfour").split()
        enrollment = EnrollmentRequest(target, tuple(engines))
        return enrollment, target.split("/")[0], None
    raise CourseAccessError("Pull requests, student code and unsupported events cannot provision access.")


def main() -> int:
    try:
        environment = os.environ
        credentials = {kind: environment.get(name, "") for kind, name in {
            "orca": "COCHEM_ORCA_ASSET_CREDENTIAL", "cfour": "COCHEM_CFOUR_ASSET_CREDENTIAL",
            "source": "COCHEM_SOURCE_CREDENTIAL"}.items() if environment.get(name)}
        config = ControllerConfig(
            repository=environment.get("COCHEM_ACCESS_CONTROLLER_REPOSITORY", ""),
            organization=environment.get("COCHEM_ACCESS_ORGANIZATION", ""),
            team_slug=environment.get("COCHEM_ACCESS_TEAM_SLUG", ""),
            app_id=environment.get("COCHEM_ACCESS_APP_ID", ""),
            app_slug=environment.get("COCHEM_ACCESS_APP_SLUG", ""),
            approved_base_repository=environment.get("COCHEM_ACCESS_BASE_REPOSITORY", ""),
            approved_base_sha=environment.get("COCHEM_ACCESS_APPROVED_BASE_SHA", ""),
            course_channel=environment.get("COCHEM_ACCESS_COURSE_CHANNEL", ""),
            allowed_starter_shas=tuple(environment.get("COCHEM_ACCESS_ALLOWED_STARTER_SHAS", "").split()),
            private_key=environment.get("COCHEM_ACCESS_APP_PRIVATE_KEY", ""),
            credentials=credentials,
        )
        event_path = Path(environment.get("GITHUB_EVENT_PATH", ""))
        if not event_path.is_file() or event_path.stat().st_size > 2 * 1024 * 1024:
            raise CourseAccessError("The trusted GitHub event file is missing or exceeds its bound.")
        event = json.loads(event_path.read_text(encoding="utf-8"))
        if not isinstance(event, dict):
            raise CourseAccessError("The trusted GitHub event is invalid.")
        controller_api = GitHubAPI(environment.get("GITHUB_TOKEN", ""))
        enrollment, author, issue_number = validate_event(event, environment, config, controller_api)
        receipt = provision_project(config, enrollment, author=author, controller_api=controller_api)
        # Only nonsecret evidence is printed. No key, credential value, encrypted
        # credential body or target's opaque secret label enters workflow logs.
        print(json.dumps(receipt, sort_keys=True))
        if issue_number is not None:
            availability = ", ".join(receipt["available"]) or "BASE without private optional components"
            controller_api.call("POST", f"/repos/{config.repository}/issues/{issue_number}/comments", {
                "body": "Private credential bindings provisioned for " + receipt["repository"] + ". Configured readers: "
                + availability + ". Create a fresh personal Codespace, let BASE finish automatic setup, "
                + "then select GitHub Actions for calculations. Private credentials were encrypted directly "
                + "into the project; no token or command is needed from you. Codespaces private module source: "
                + receipt["codespaces_source"] + ". If unavailable, ask the instructor to configure module-source "
                + "access before expecting TOPOS/TORQ automatic installation. Actual reader validity, module installation "
                + "and engine scientific execution are checked by BASE setup and the requested calculation, not by this enrollment job."})
        return 0
    except CourseAccessError as exc:
        # CourseAccessError messages are controlled strings, never response data.
        print("CoChem project access: " + str(exc), file=sys.stderr)
        return 1
    except (ValueError, TypeError, KeyError, OSError):
        print("CoChem project access: invalid controller configuration or event; nothing was certified ready.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
