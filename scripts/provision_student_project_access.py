"""Instructor-only GitHub Actions entry point for private project enrollment."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import sys
import time
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
deprovision_project = _module.deprovision_project
reconcile_project = _module.reconcile_project
repository_name = _module.repository_name
ControllerInboxStore = _module.ControllerInboxStore
sync_calculation_access = _module.sync_calculation_access


def validate_controller(event: dict, environment: dict[str, str], config: ControllerConfig,
                        controller_api: GitHubAPI) -> None:
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


def validate_event(event: dict, environment: dict[str, str], config: ControllerConfig,
                   controller_api: GitHubAPI) -> tuple[EnrollmentRequest | None, str, int | None]:
    validate_controller(event, environment, config, controller_api)
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
        operation = inputs.get("operation", "provision")
        if not isinstance(operation, str) or operation not in {"provision", "reconcile", "deprovision", "sweep"}:
            raise CourseAccessError("Select a supported instructor access lifecycle operation.")
        if operation == "sweep":
            return None, actor, None
        target = repository_name(inputs.get("project_repository", ""))
        engine_selection = inputs.get("engines", "orca cfour")
        if not isinstance(engine_selection, str):
            raise CourseAccessError("The selected engine list is invalid.")
        engines = engine_selection.split()
        enrollment = EnrollmentRequest(target, tuple(engines))
        return enrollment, target.split("/")[0], None
    raise CourseAccessError("Pull requests, student code and unsupported events cannot provision access.")


def _issue_request(issue: dict) -> tuple[EnrollmentRequest, str, str]:
    """Fresh immutable issue identity + actual owner + canonical request data."""
    if (not isinstance(issue, dict) or "pull_request" in issue or issue.get("state") != "open"
            or type(issue.get("id")) is not int or not 0 < issue["id"] < 10**20
            or type(issue.get("number")) is not int or issue["number"] <= 0):
        raise CourseAccessError("The enrollment inbox item is not an open issue.")
    user = issue.get("user", {})
    author = user.get("login") if isinstance(user, dict) else None
    if (not isinstance(author, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", author)
            or type(user.get("id")) is not int or user["id"] <= 0):
        raise CourseAccessError("The enrollment issue owner could not be verified.")
    enrollment = parse_enrollment(issue.get("body", ""))
    if enrollment.repository.split("/")[0].lower() != author.lower():
        raise CourseAccessError("Students may enroll only their own private project.")
    identity = {"issue_id": issue["id"], "owner_id": user["id"],
                "repository": enrollment.repository.lower(), "engines": sorted(enrollment.engines)}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return enrollment, author, fingerprint


def sweep_inbox(config: ControllerConfig, controller_api: GitHubAPI, *,
                app_api: GitHubAPI | None = None, authority_api: GitHubAPI | None = None,
                max_attempts: int = 20, max_pages: int = 10,
                time_budget_seconds: float = 420) -> dict:
    """Bounded round-robin reconciliation of durable issues, not Actions runs.

    A canceled pending run loses only a wake-up. The scheduled/manual sweeper
    revisits the issue. Cursor progress precedes each attempt, so invalid or
    temporarily blocked items cannot monopolize every subsequent run. Lifecycle
    retries are at-least-once; signed generation ownership makes interruption
    recovery cleanup-safe, rather than claiming a multi-API transaction.
    """
    if (type(max_attempts) is not int or not 1 <= max_attempts <= 20
            or type(max_pages) is not int or not 1 <= max_pages <= 10
            or type(time_budget_seconds) not in {int, float} or not 0 < time_budget_seconds <= 420):
        raise CourseAccessError("The controller inbox sweep budget is invalid.")
    store = ControllerInboxStore(config, app_api=app_api)
    cursor = store.read("COCHEM_ACCESS_INBOX_CURSOR") or {"issue_id": 0, "next_page": 1}
    if (set(cursor) != {"issue_id", "next_page"} or type(cursor["issue_id"]) is not int
            or cursor["issue_id"] < 0 or type(cursor["next_page"]) is not int
            or not 1 <= cursor["next_page"] < 2**31):
        raise CourseAccessError("Controller inbox cursor is invalid.")
    started = time.monotonic()
    issues = []
    seen_ids, seen_numbers = set(), set()
    truncated = True
    next_page = cursor["next_page"]
    for page in range(next_page, next_page + max_pages):
        values = controller_api.call("GET", f"/repos/{config.repository}/issues?state=open&sort=created&direction=asc&per_page=100&page={page}")
        if not isinstance(values, list) or len(values) > 100:
            raise CourseAccessError("GitHub returned invalid bounded inbox metadata.")
        for value in values:
            if not isinstance(value, dict):
                raise CourseAccessError("GitHub returned invalid inbox issue metadata.")
            if "pull_request" in value:
                continue
            identifier, number = value.get("id"), value.get("number")
            if (type(identifier) is not int or not 0 < identifier < 10**20
                    or type(number) is not int or number <= 0
                    or identifier in seen_ids or number in seen_numbers):
                raise CourseAccessError("GitHub returned duplicate or invalid inbox issue identities.")
            seen_ids.add(identifier)
            seen_numbers.add(number)
            issues.append(value)
        if len(values) < 100:
            truncated = False
            next_page = 1
            break
        next_page = page + 1
        if time.monotonic() - started >= time_budget_seconds:
            break
    # Retain this window until every listed ID has been visited. Advancing the
    # scan window immediately would let a later high ID reset first-window
    # priority, allowing its same twenty failing requests to starve request 21.
    # Repeated complete cycles also recover shifting offsets after issue closes.
    issues = sorted((issue for issue in issues if issue["id"] > cursor["issue_id"]),
                    key=lambda issue: issue["id"])
    summary = {"schema": "cochem.controller-inbox-sweep.v1", "processed": 0, "failed": 0,
               "skipped": 0, "held": 0, "changed": 0, "scan_truncated": truncated,
               "next_scan_page": cursor["next_page"], "window_complete": False,
               "failure_details": [], "failure_details_truncated": False}
    def failure(issue: dict, message: str) -> None:
        summary["failed"] += 1
        if len(summary["failure_details"]) < 100:
            summary["failure_details"].append({"issue_number": issue["number"], "issue_id": issue["id"],
                                               "reason": message[:512]})
        else:
            summary["failure_details_truncated"] = True
    attempts = 0
    window_complete = True
    for listed in issues:
        if attempts >= max_attempts or time.monotonic() - started >= time_budget_seconds:
            window_complete = False
            break
        # This signed cursor is progress, never authorization or deletion scope.
        store.write("COCHEM_ACCESS_INBOX_CURSOR", {"issue_id": listed["id"], "next_page": cursor["next_page"]})
        key = "COCHEM_ACCESS_INBOX_ISSUE_" + str(listed["id"])
        try:
            issue = controller_api.call("GET", f"/repos/{config.repository}/issues/{listed['number']}")
            if not isinstance(issue, dict) or issue.get("id") != listed["id"] or issue.get("number") != listed["number"]:
                raise CourseAccessError("The inbox issue identity changed.")
            enrollment, author, fingerprint = _issue_request(issue)
            expected_repository_id, held = store.held_project(enrollment.repository)
            if held:
                summary["held"] += 1
                continue
            saved = store.read(key)
            if saved is not None and (set(saved) != {"fingerprint", "status", "receipt", "notified"}
                    or not isinstance(saved["status"], str) or saved["status"] not in {"pending", "done"}
                    or not isinstance(saved["fingerprint"], str)
                    or not re.fullmatch(r"[a-f0-9]{64}", saved["fingerprint"])
                    or type(saved["notified"]) is not bool
                    or not isinstance(saved["receipt"], dict)):
                raise CourseAccessError("The controller inbox receipt is invalid.")
            if saved is not None and (saved["status"] == "pending" and saved["receipt"] != {}
                    or saved["status"] == "done" and (
                        saved["receipt"].get("schema") != _module.RECEIPT_SCHEMA
                        or saved["receipt"].get("status") != "provisioned"
                        or type(saved["receipt"].get("repository_id")) is not int
                        or saved["receipt"]["repository_id"] <= 0)):
                raise CourseAccessError("The controller inbox completion receipt is invalid.")
            if saved is not None and saved["fingerprint"] == fingerprint and saved["status"] == "done":
                if (str(saved["receipt"].get("repository", "")).lower() != enrollment.repository.lower()
                        or saved["receipt"]["repository_id"] != expected_repository_id):
                    raise CourseAccessError("The controller inbox receipt project identity differs.")
                summary["skipped"] += 1
            else:
                attempts += 1
                saved = {"fingerprint": fingerprint, "status": "pending", "receipt": {}, "notified": False}
                store.write(key, saved)
                # Ignore stale webhook bodies and cancellation/edits observed
                # while this attempt was prepared. GitHub offers no transaction
                # combining an issue read and the subsequent project writes.
                fresh = controller_api.call("GET", f"/repos/{config.repository}/issues/{issue['number']}")
                _, fresh_author, fresh_fingerprint = _issue_request(fresh)
                if (fresh.get("id") != issue["id"] or fresh.get("number") != issue["number"]
                        or fresh_author != author or fresh_fingerprint != fingerprint):
                    summary["changed"] += 1
                    continue
                receipt = provision_project(config, enrollment, author=author, controller_api=controller_api,
                                            app_api=app_api, authority_api=authority_api,
                                            expected_repository_id=expected_repository_id)
                if receipt.get("status") != "provisioned":
                    failure(listed, "Owned credential cleanup remains pending; retry instructor reconciliation.")
                    continue
                saved.update(status="done", receipt=receipt)
                # Completion precedes notification: failed comments never cause
                # another credential rotation on the next sweep.
                store.write(key, saved)
                summary["processed"] += 1
            if not saved["notified"]:
                controller_api.call("POST", f"/repos/{config.repository}/issues/{issue['number']}/comments",
                                    {"body": enrollment_comment(saved["receipt"])})
                saved["notified"] = True
                store.write(key, saved)
        except CourseAccessError as exc:
            # Do not print issue bodies or upstream responses. The issue remains
            # durable for a later sweep; continue the rest of the cohort.
            failure(listed, str(exc))
    if window_complete:
        # Only now move beyond the bounded window, resetting its visit cursor.
        # A crash before this write resumes the old window safely next time.
        store.write("COCHEM_ACCESS_INBOX_CURSOR", {"issue_id": 0, "next_page": next_page})
        summary["next_scan_page"] = next_page
        summary["window_complete"] = True
    return summary


def maintain_project(config: ControllerConfig, enrollment: EnrollmentRequest, operation: str,
                     *, author: str, controller_api: GitHubAPI,
                     app_api: GitHubAPI | None = None, authority_api: GitHubAPI | None = None) -> dict:
    """Call only after authenticated instructor dispatch validation."""
    store = ControllerInboxStore(config, app_api=app_api)
    expected_repository_id, held = store.held_project(enrollment.repository)
    if operation == "deprovision":
        store.hold_repository_id(expected_repository_id, True)
        return deprovision_project(config, enrollment.repository, controller_api=controller_api, app_api=app_api,
                                   expected_repository_id=expected_repository_id)
    if operation == "reconcile":
        if held:
            return deprovision_project(config, enrollment.repository, controller_api=controller_api, app_api=app_api,
                                       expected_repository_id=expected_repository_id)
        return reconcile_project(config, enrollment, controller_api=controller_api, app_api=app_api,
                                 authority_api=authority_api, expected_repository_id=expected_repository_id)
    if operation != "provision":
        raise CourseAccessError("Select a supported instructor lifecycle operation.")
    receipt = provision_project(config, enrollment, author=author, controller_api=controller_api,
                                app_api=app_api, authority_api=authority_api,
                                expected_repository_id=expected_repository_id)
    if receipt.get("status") == "provisioned":
        store.hold_repository_id(expected_repository_id, False)
    return receipt


def enrollment_comment(receipt: dict) -> str:
    """Explain provisioned access without certifying engine or module execution."""
    availability = ", ".join("private module downloads" if name == "source" else name.upper()
                             for name in receipt["available"]) or "BASE without optional components"
    return (
        "Your project " + receipt["repository"] + " is connected to the lab for " + availability + ".\n\n"
        + "1. Open your project's **Code → Codespaces** menu and create a **new Codespace** from its default branch. "
        + "Authorize the requested access to this project so BASE can submit calculations and retrieve results. "
        + "Rebuilding an existing Codespace does not update these permissions.\n"
        + "2. Let BASE finish automatic setup, then open its dashboard.\n"
        + "3. Under **Start here**, select **GitHub Actions** and click **Check ORCA & CFOUR**. "
        + "That check confirms whether the selected engines can be downloaded; a calculation confirms actual execution.\n\n"
        + "No terminal commands or access tokens are needed from you. "
        + "Public TOPOS/TORQ source downloads do not require a private source credential. "
        + "Module installation has not been verified by this access setup; BASE checks installation in your new Codespace."
    )


def credential_targets(environment: dict[str, str], credentials: dict[str, str]) -> dict:
    """Read only the immutable controller's reviewed manifests/configuration."""
    targets = {}
    for engine in {"orca", "cfour"} & credentials.keys():
        path = Path(__file__).resolve().with_name(engine + "-distribution.json")
        if not path.is_file() or path.stat().st_size > 65536:
            raise CourseAccessError("The reviewed engine-reader target manifest is unavailable.")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise CourseAccessError("The reviewed engine-reader target manifest is invalid.")
        targets[engine] = {name: value.get(name) for name in (
            "repository", "release_tag", "archive_name", "sha256")}
    if ("source" in credentials and environment.get("COCHEM_ACCESS_SOURCE_REPOSITORY")
            and environment.get("COCHEM_ACCESS_SOURCE_REVISION")):
        targets["source"] = {"repository": environment.get("COCHEM_ACCESS_SOURCE_REPOSITORY", ""),
                             "revision": environment.get("COCHEM_ACCESS_SOURCE_REVISION", "")}
    return targets


def main() -> int:
    try:
        environment = os.environ
        credentials = {kind: environment.get(name, "") for kind, name in {
            "orca": "COCHEM_ORCA_ASSET_CREDENTIAL", "cfour": "COCHEM_CFOUR_ASSET_CREDENTIAL",
            "source": "COCHEM_SOURCE_CREDENTIAL",
            "colab": "COLAB_OFFLOAD_DISPATCH_TOKEN"}.items() if environment.get(name)}
        if not credentials.get("colab") and environment.get("COCHEM_COLAB_ASSET_CREDENTIAL"):
            credentials["colab"] = environment.get("COCHEM_COLAB_ASSET_CREDENTIAL", "")
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
            credential_targets=credential_targets(environment, credentials),
        )
        event_path = Path(environment.get("GITHUB_EVENT_PATH", ""))
        if not event_path.is_file() or event_path.stat().st_size > 2 * 1024 * 1024:
            raise CourseAccessError("The trusted GitHub event file is missing or exceeds its bound.")
        event = json.loads(event_path.read_text(encoding="utf-8"))
        if not isinstance(event, dict):
            raise CourseAccessError("The trusted GitHub event is invalid.")
        controller_api = GitHubAPI(environment.get("GITHUB_TOKEN", ""))
        kind = environment.get("GITHUB_EVENT_NAME")
        if kind in {"issues", "schedule"}:
            validate_controller(event, environment, config, controller_api)
            if kind == "issues" and event.get("action") not in {"opened", "reopened", "edited"}:
                raise CourseAccessError("Unsupported enrollment inbox wake-up.")
            summary = sweep_inbox(config, controller_api)
            print(json.dumps(summary, sort_keys=True))
            return 1 if summary["failed"] else 0
        enrollment, author, _ = validate_event(event, environment, config, controller_api)
        operation = (event.get("inputs", {}).get("operation", "provision")
                     if kind == "workflow_dispatch" else "provision")
        if operation == "sweep":
            summary = sweep_inbox(config, controller_api)
            print(json.dumps(summary, sort_keys=True))
            return 1 if summary["failed"] else 0
        receipt = maintain_project(config, enrollment, operation, author=author, controller_api=controller_api)
        # Only nonsecret evidence is printed. No key, credential value, encrypted
        # credential body or target's opaque secret label enters workflow logs.
        print(json.dumps(receipt, sort_keys=True))
        if receipt["status"] == "cleanup_pending":
            print("CoChem project access: owned credential cleanup remains pending; retry instructor reconciliation.", file=sys.stderr)
            return 1
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
