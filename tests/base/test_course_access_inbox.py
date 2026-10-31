"""Local inbox/HTTP/RSA/libsodium protocol checks; never live GitHub proof.

The controller and lifecycle functions run unchanged against a loopback REST
peer. Twenty distinct owners/projects have separate actual encrypted stores.
No student source executes and no licensed calculation is claimed.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import secrets
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from scripts import provision_student_project_access as controller
from tests.base.test_course_project_access import (
    ProtocolConfiguration, ProtocolHandler, ProtocolServer, config_for,
)


class InboxHandler(ProtocolHandler):
    def operation(self, method):
        state = self.server
        parsed = urlsplit(self.path)
        if method == "GET" and parsed.path.startswith("/repos/"):
            repository = parsed.path.removeprefix("/repos/")
            if repository in state.projects:
                count = state.identity_fetches.get(repository, 0) + 1
                state.identity_fetches[repository] = count
                changed_id = state.change_identity_on_fetch.get((repository, count))
                if changed_id is not None:
                    state.projects[repository].project_id = changed_id
        prefix = "/repos/Lab/Controller/issues"
        if parsed.path == prefix or parsed.path.startswith(prefix + "/"):
            assert self.headers.get("Authorization") == "Bearer " + state.controller_token
            if parsed.path == prefix:
                query = parse_qs(parsed.query)
                assert query["state"] == ["open"] and query["sort"] == ["created"]
                assert query["direction"] == ["asc"] and query["per_page"] == ["100"]
                page = int(query["page"][0])
                state.pages.append(page)
                values = sorted((value for value in state.inbox.values() if value["state"] == "open"),
                                key=lambda value: value["id"])
                self.answer(values[(page - 1) * 100:page * 100])
                return
            number = int(parsed.path[len(prefix) + 1:].split("/")[0])
            if method == "GET":
                state.fetches[number] = state.fetches.get(number, 0) + 1
                hook = state.change_on_fetch.get((number, state.fetches[number]))
                if hook:
                    state.inbox[number].update(hook)
                self.answer(state.inbox[number])
            else:
                assert method == "POST" and parsed.path.endswith("/comments")
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if state.fail_comments:
                    state.fail_comments -= 1
                    self.answer({}, 503)
                else:
                    state.comments.append((number, body))
                    self.answer({"id": len(state.comments)}, 201)
            return
        # Refuse a completion receipt after the actual project transaction has
        # succeeded. The next unchanged production sweep must recover safely.
        if method in {"POST", "PATCH"} and "/Controller/actions/variables" in parsed.path:
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            payload = json.loads(raw)
            self.rfile = io.BytesIO(raw)
            if payload["name"].startswith("COCHEM_ACCESS_PROJECT_") and state.identity_after_grant:
                owned = json.loads(payload["value"])["payload"]
                if owned.get("state") == "active":
                    repository, replacement_id = state.identity_after_grant
                    state.projects[repository].project_id = replacement_id
                    state.identity_after_grant = None
            if payload["name"].startswith("COCHEM_ACCESS_INBOX_ISSUE_"):
                data = json.loads(payload["value"])["payload"]["data"]
                if state.fail_completion and data["status"] == "done":
                    state.fail_completion -= 1
                    self.answer({}, 503)
                    return
        super().operation(method)


@pytest.fixture
def cohort(request):
    count = getattr(request, "param", 1)
    root = ProtocolServer(ProtocolConfiguration())
    root.RequestHandlerClass = InboxHandler
    root.projects = {}
    root.inbox, root.fetches, root.change_on_fetch = {}, {}, {}
    root.identity_fetches, root.change_identity_on_fetch = {}, {}
    root.identity_after_grant = None
    root.comments, root.pages = [], []
    root.fail_comments = root.fail_completion = 0
    for number in range(1, count + 1):
        author = f"student{number:02d}"
        repository = author + "/project"
        project = ProtocolServer(ProtocolConfiguration(project_repository=repository,
            project_id=1000 + number, project_owner_login=author))
        project.signing_key = root.signing_key
        project.tokens = root.tokens
        project.controller_token = root.controller_token
        project.controller_variables = root.controller_variables
        root.projects[repository] = project
        root.inbox[number] = {"id": 10000 + number, "number": number, "state": "open",
            "user": {"login": author, "id": 20000 + number},
            "body": json.dumps(controller.EnrollmentRequest(repository, ("orca",)).to_dict())}
    config = config_for(root, credentials={"orca": secrets.token_urlsafe(32)})
    api = controller.GitHubAPI(root.controller_token, api_url=root.url, allow_loopback=True)
    app = controller.GitHubAPI(controller._module.app_jwt(config.app_id, config.private_key),
                               api_url=root.url, allow_loopback=True)
    authority = controller.GitHubAPI(api_url=root.url, allow_loopback=True)
    worker = threading.Thread(target=root.serve_forever, daemon=True)
    worker.start()
    try:
        yield root, config, api, app, authority
    finally:
        root.shutdown()
        root.server_close()
        worker.join(timeout=5)
        assert not worker.is_alive()
        for project in root.projects.values():
            project.server_close()


def sweep(cohort, **kwargs):
    root, config, api, app, authority = cohort
    return controller.sweep_inbox(config, api, app_api=app, authority_api=authority, **kwargs)


def store_for(cohort):
    _, config, _, app, _ = cohort
    return controller.ControllerInboxStore(config, app_api=app)


def project_snapshot(root):
    return {name: (dict(project.variables), dict(project.secret_values), dict(project.codespaces_values),
                   project.project_revision, project.project_devcontainer, project.project_ring)
            for name, project in root.projects.items()}


@pytest.mark.parametrize("cohort", [20], indirect=True)
def test_twenty_durable_requests_survive_lost_wakeups_and_repeated_sweep(cohort, tmp_path):
    root, config, _, _, _ = cohort
    # The twenty requests already exist in the durable inbox. Execute just one
    # surviving sweep, as if GitHub discarded every other pending wake-up.
    first = sweep(cohort)
    assert first["processed"] == 20 and first["failed"] == 0
    assert len(root.comments) == 20 and not first["scan_truncated"]
    ledger = json.dumps(root.controller_variables)
    assert config.private_key not in ledger and config.credentials["orca"] not in ledger
    for repository, project in root.projects.items():
        assert list(project.secret_values.values()) == [config.credentials["orca"]]
        assert len(project.codespaces_values) == 2
        assert project.codespaces_values["COCHEM_ACCESS_CONTROLLER_REPOSITORY"] == config.repository
        assert config.private_key not in project.secret_values.values()
        assert config.private_key not in project.codespaces_values.values()
        grant = json.loads(project.project_devcontainer)["customizations"]["codespaces"]["repositories"]
        assert set(grant) == {repository}
        assert json.loads(project.project_ring)["files"][".devcontainer/devcontainer.json"] == hashlib.sha256(project.project_devcontainer).hexdigest()
        signed = json.loads(root.controller_variables[f"COCHEM_ACCESS_PROJECT_{project.project_id}"])
        assert signed["payload"]["state"] == "active" and len(signed["payload"]["actions"]) == 1
        project.writes.clear()
    before = project_snapshot(root)
    second = sweep(cohort)
    assert second["processed"] == 0 and second["skipped"] == 20 and second["failed"] == 0
    assert project_snapshot(root) == before and len(root.comments) == 20
    assert all(project.writes == [] for project in root.projects.values())
    evidence = {"scope": "local loopback HTTP/RSA/libsodium protocol; not GitHub or student service acceptance",
        "distinct_project_owners": 20, "durable_requests": 20, "surviving_wakeups_executed": 1,
        "first_sweep": first, "repeat_sweep": second,
        "repeat_project_mutations": 0, "private_key_delivered": False,
        "source_sha256": {path: hashlib.sha256((Path(__file__).resolve().parents[2] / path).read_bytes()).hexdigest()
            for path in ("scripts/provision_student_project_access.py",
                         "src/cochem_base/interfaces/course_access.py",
                         ".github/workflows/course_project_access.yml")}}
    output = Path(os.environ.get("COCHEM_QUEUE_EVIDENCE_DIR", str(tmp_path)))
    output.mkdir(parents=True, exist_ok=True)
    (output / "twenty-request-local-protocol.json").write_text(json.dumps(evidence, indent=2) + "\n")


def test_failed_notification_retries_comment_without_rotating_credentials(cohort):
    root, *_ = cohort
    root.fail_comments = 1
    first = sweep(cohort)
    assert first["processed"] == 1 and first["failed"] == 1
    before = project_snapshot(root)
    for project in root.projects.values():
        project.writes.clear()
    second = sweep(cohort)
    assert second["processed"] == 0 and second["skipped"] == 1 and second["failed"] == 0
    assert project_snapshot(root) == before and len(root.comments) == 1
    assert all(project.writes == [] for project in root.projects.values())


def test_interruption_after_provision_before_receipt_recovers_owned_generation(cohort):
    root, config, *_ = cohort
    root.fail_completion = 1
    assert sweep(cohort)["failed"] == 1
    store = store_for(cohort)
    assert store.read("COCHEM_ACCESS_INBOX_ISSUE_10001")["status"] == "pending"
    assert sweep(cohort)["processed"] == 1
    project = next(iter(root.projects.values()))
    assert list(project.secret_values.values()) == [config.credentials["orca"]]
    owned = json.loads(root.controller_variables[f"COCHEM_ACCESS_PROJECT_{project.project_id}"])["payload"]
    assert owned["state"] == "active" and len(owned["actions"]) == 1
    assert store.read("COCHEM_ACCESS_INBOX_ISSUE_10001")["status"] == "done"


@pytest.mark.parametrize("change", [{"state": "closed"}, {"body": json.dumps({
    "schema": controller._module.REQUEST_SCHEMA, "repository": "student01/project", "engines": []})}])
def test_close_or_edit_observed_before_mutation_preserves_project(cohort, change):
    root, *_ = cohort
    root.change_on_fetch[(1, 2)] = change
    before = project_snapshot(root)
    result = sweep(cohort)
    assert result["processed"] == 0 and result["failed"] + result["changed"] == 1
    assert project_snapshot(root) == before
    assert all(project.writes == [] for project in root.projects.values())


def test_edit_changes_canonical_request_but_whitespace_and_reopen_do_not_replay(cohort):
    root, *_ = cohort
    assert sweep(cohort)["processed"] == 1
    before = project_snapshot(root)
    root.inbox[1]["body"] = "\n  " + root.inbox[1]["body"] + " \n"
    assert sweep(cohort)["skipped"] == 1
    root.inbox[1]["state"] = "closed"
    assert sweep(cohort)["processed"] == 0
    root.inbox[1]["state"] = "open"
    assert sweep(cohort)["skipped"] == 1
    assert project_snapshot(root) == before
    root.inbox[1]["body"] = json.dumps(controller.EnrollmentRequest("student01/project", ()).to_dict())
    assert sweep(cohort)["processed"] == 1
    assert next(iter(root.projects.values())).secret_values == {}


def test_instructor_withdrawal_hold_survives_reconcile_and_explicit_provision_releases(cohort):
    root, config, api, app, authority = cohort
    assert sweep(cohort)["processed"] == 1
    request = controller.EnrollmentRequest("student01/project", ("orca",))
    options = {"author": "student01", "controller_api": api, "app_api": app, "authority_api": authority}
    assert controller.maintain_project(config, request, "deprovision", **options)["status"] == "deprovisioned"
    assert store_for(cohort).held(request.repository)
    # A new/edited student request cannot undo the instructor's hold.
    root.inbox[1]["body"] = json.dumps(controller.EnrollmentRequest(request.repository, ()).to_dict())
    assert sweep(cohort)["held"] == 1
    assert controller.maintain_project(config, request, "reconcile", **options)["status"] == "deprovisioned"
    assert store_for(cohort).held(request.repository)
    assert controller.maintain_project(config, request, "provision", **options)["status"] == "provisioned"
    assert not store_for(cohort).held(request.repository)


def test_failed_withdrawal_still_holds_back_pending_request(cohort):
    root, config, api, app, authority = cohort
    assert sweep(cohort)["processed"] == 1
    project = next(iter(root.projects.values()))
    project.fail_variable = True
    with pytest.raises(controller.CourseAccessError):
        controller.maintain_project(config, controller.EnrollmentRequest("student01/project"), "deprovision",
            author="student01", controller_api=api, app_api=app, authority_api=authority)
    assert store_for(cohort).held("student01/project")
    assert sweep(cohort)["held"] == 1


def test_withdrawal_hold_follows_immutable_project_id_after_rename(cohort):
    root, config, api, app, authority = cohort
    assert sweep(cohort)["processed"] == 1
    request = controller.EnrollmentRequest("student01/project", ("orca",))
    controller.maintain_project(config, request, "deprovision", author="student01",
        controller_api=api, app_api=app, authority_api=authority)
    project = root.projects.pop(request.repository)
    project.project_repository = "student01/renamed-project"
    root.projects[project.project_repository] = project
    root.inbox[1]["body"] = json.dumps(controller.EnrollmentRequest(project.project_repository, ("orca",)).to_dict())
    project.writes.clear()
    result = sweep(cohort)
    # Check the hold decision itself: an unrelated source/ownership-name refusal
    # must not accidentally make this rename control look successful.
    assert result["held"] == 1 and result["failed"] == result["processed"] == 0
    assert project.writes == [] and project.secret_values == {}
    assert store_for(cohort).held(project.project_repository)
    held = store_for(cohort).read("COCHEM_ACCESS_INBOX_HOLD_1001")
    assert held == {"repository_id": 1001, "held": True}


def test_hold_before_first_grant_survives_rename_and_name_reuse_does_not_inherit_it(cohort):
    root, config, api, app, authority = cohort
    # A withdrawal can save its hold before finding that ownership never existed.
    with pytest.raises(controller.CourseAccessError, match="ownership"):
        controller.maintain_project(config, controller.EnrollmentRequest("student01/project"), "deprovision",
            author="student01", controller_api=api, app_api=app, authority_api=authority)
    project = root.projects.pop("student01/project")
    project.project_repository = "student01/renamed-project"
    root.projects[project.project_repository] = project
    root.inbox[1]["body"] = json.dumps(controller.EnrollmentRequest(project.project_repository, ("orca",)).to_dict())
    assert sweep(cohort)["held"] == 1
    assert project.writes == []
    # A different immutable repository using a former name is a different hold
    # identity. It still needs the ordinary complete authorization checks.
    project.project_id = 2001
    assert not store_for(cohort).held(project.project_repository)
    assert store_for(cohort).read("COCHEM_ACCESS_INBOX_HOLD_1001")["held"] is True


def test_held_repository_cannot_replace_unheld_name_between_precheck_and_provision(cohort):
    root, *_ = cohort
    store = store_for(cohort)
    store.write("COCHEM_ACCESS_INBOX_HOLD_2001", {"repository_id": 2001, "held": True})
    # First selected-App metadata read sees unheld repository1001. Before the
    # lifecycle's independent context read, held repository2001 takes its name.
    root.change_identity_on_fetch[("student01/project", 2)] = 2001
    result = sweep(cohort)
    project = root.projects["student01/project"]
    assert project.project_id == 2001 and result["failed"] == 1 and result["processed"] == 0
    assert "identity changed" in result["failure_details"][0]["reason"]
    assert project.writes == [] and project.secret_values == {} and project.codespaces_values == {}
    assert "COCHEM_ACCESS_PROJECT_2001" not in root.controller_variables
    assert sweep(cohort)["held"] == 1


@pytest.mark.parametrize("cohort", [3], indirect=True)
def test_invalid_signed_receipt_type_refuses_only_that_request(cohort):
    root, *_ = cohort
    store_for(cohort).write("COCHEM_ACCESS_INBOX_ISSUE_10001",
        {"fingerprint": "0" * 64, "status": [], "receipt": {}, "notified": False})
    result = sweep(cohort)
    assert result["failed"] == 1 and result["processed"] == 2
    assert root.projects["student01/project"].writes == []


@pytest.mark.parametrize("operation,held,member", [
    ("provision", False, True), ("deprovision", False, True),
    ("reconcile", False, True), ("reconcile", True, True), ("reconcile", False, False),
])
def test_every_instructor_lifecycle_branch_refuses_changed_target_before_project_writes(cohort, operation, held, member):
    root, config, api, app, authority = cohort
    store = store_for(cohort)
    store.hold_repository_id(1001, held)
    store.hold_repository_id(2001, True)
    root.projects["student01/project"].active = member
    root.change_identity_on_fetch[("student01/project", 2)] = 2001
    with pytest.raises(controller.CourseAccessError, match="identity changed"):
        controller.maintain_project(config, controller.EnrollmentRequest("student01/project", ("orca",)), operation,
            author="student01", controller_api=api, app_api=app, authority_api=authority)
    assert root.projects["student01/project"].writes == []
    assert store.read("COCHEM_ACCESS_INBOX_HOLD_2001")["held"] is True
    assert "COCHEM_ACCESS_PROJECT_2001" not in root.controller_variables


def test_instructor_provision_releases_only_granted_immutable_id_after_name_swap(cohort):
    root, config, api, app, authority = cohort
    store = store_for(cohort)
    store.hold_repository_id(1001, True)
    store.hold_repository_id(2001, True)
    root.identity_after_grant = ("student01/project", 2001)
    receipt = controller.maintain_project(config, controller.EnrollmentRequest("student01/project", ("orca",)),
        "provision", author="student01", controller_api=api, app_api=app, authority_api=authority)
    assert receipt["status"] == "provisioned"
    assert root.projects["student01/project"].project_id == 2001
    assert store.read("COCHEM_ACCESS_INBOX_HOLD_1001")["held"] is False
    assert store.read("COCHEM_ACCESS_INBOX_HOLD_2001")["held"] is True
    # Captured hold target, provision target, then required post-pair readback.
    assert root.identity_fetches["student01/project"] == 3


def test_historical_config_only_done_receipt_is_not_automatically_upgraded(cohort):
    """Controlled old-schema protocol state; not a claimed live legacy receipt."""
    root, *_ = cohort
    assert sweep(cohort)["processed"] == 1
    store = store_for(cohort)
    key = "COCHEM_ACCESS_INBOX_ISSUE_10001"
    saved = store.read(key)
    # Preserve the actual generated configuration; the old deployment paired
    # it with the canonical ring and had no new paired-binding receipt fields.
    for name in ("codespaces_binding_schema", "codespaces_ring_sha", "ring_template_sha",
                 "ring_current_sha", "project_source_digest", "source_state"):
        saved["receipt"].pop(name)
    store.write(key, saved)
    project = root.projects["student01/project"]
    project.project_ring = project.infrastructure_ring
    assert project.project_devcontainer != project.devcontainer
    project.writes.clear()
    before = project_snapshot(root)
    comments = len(root.comments)
    result = sweep(cohort)
    assert result["skipped"] == 1 and result["processed"] == result["failed"] == 0
    assert project_snapshot(root) == before and project.writes == []
    assert store.read(key) == saved and len(root.comments) == comments
    assert project.project_ring == project.infrastructure_ring


@pytest.mark.parametrize("notified", [True, False])
def test_completed_receipt_cannot_certify_reused_name_with_different_repository_id(cohort, notified):
    root, *_ = cohort
    assert sweep(cohort)["processed"] == 1
    store = store_for(cohort)
    saved = store.read("COCHEM_ACCESS_INBOX_ISSUE_10001")
    assert saved["receipt"]["repository_id"] == 1001
    saved["notified"] = notified
    store.write("COCHEM_ACCESS_INBOX_ISSUE_10001", saved)
    project = root.projects["student01/project"]
    project.project_id = 2001
    project.writes.clear()
    comments = len(root.comments)
    result = sweep(cohort)
    assert result["processed"] == result["skipped"] == 0 and result["failed"] == 1
    assert "receipt project identity differs" in result["failure_details"][0]["reason"]
    assert project.writes == [] and len(root.comments) == comments


@pytest.mark.parametrize("cohort", [3], indirect=True)
def test_invalid_owner_body_and_tampered_receipt_do_not_starve_later_request(cohort):
    root, *_ = cohort
    root.inbox[1]["user"]["login"] = "another-owner"
    root.inbox[2]["body"] = "$(untrusted enrollment is never shell code)"
    result = sweep(cohort)
    assert result["processed"] == 1 and result["failed"] == 2
    assert root.projects["student01/project"].writes == []
    assert root.projects["student02/project"].writes == []
    root.inbox[1]["user"]["login"] = "student01"
    root.controller_variables["COCHEM_ACCESS_INBOX_ISSUE_10001"] = '{"payload":{},"signature":"AA=="}'
    root.inbox[2]["body"] = json.dumps(controller.EnrollmentRequest("student02/project", ("orca",)).to_dict())
    result = sweep(cohort)
    assert result["processed"] == 1 and result["failed"] == 1 and result["skipped"] == 1
    assert root.projects["student01/project"].writes == []


@pytest.mark.parametrize("cohort", [3], indirect=True)
def test_signed_cursor_resumes_bounded_attempts_without_losing_requests(cohort):
    root, *_ = cohort
    for _ in range(3):
        assert sweep(cohort, max_attempts=1)["processed"] == 1
    assert len(root.comments) == 3
    assert sweep(cohort)["skipped"] == 3


@pytest.mark.parametrize("cohort", [3], indirect=True)
def test_failed_oldest_request_does_not_take_every_bounded_sweep(cohort):
    root, *_ = cohort
    root.projects["student01/project"].fail_secret_put = True
    first = sweep(cohort, max_attempts=1)
    assert first["failed"] == 1 and first["failure_details"][0]["issue_number"] == 1
    assert sweep(cohort, max_attempts=1)["processed"] == 1
    assert sweep(cohort, max_attempts=1)["processed"] == 1
    root.projects["student01/project"].fail_secret_put = False
    assert sweep(cohort, max_attempts=1)["processed"] == 1
    assert len(root.comments) == 3


def test_pagination_and_scan_limit_are_explicit(cohort):
    root, *_ = cohort
    # One hundred non-enrollment issues fill the first page; the genuine
    # request must be discovered on the second page without trusting its event.
    for number in range(101, 201):
        root.inbox[number] = {"id": number, "number": number, "state": "open",
            "user": {"login": "student01", "id": 20001}, "body": "course question"}
    first = sweep(cohort, max_pages=1)
    assert first["scan_truncated"] and first["processed"] == 0
    root.pages.clear()
    second = sweep(cohort)
    assert root.pages == [2] and second["processed"] == 1 and not second["scan_truncated"]


def test_repeated_sweep_advances_beyond_ten_pages_instead_of_losing_new_requests(cohort):
    root, *_ = cohort
    for number in range(101, 1102):
        root.inbox[number] = {"id": number, "number": number, "state": "open", "pull_request": {}}
    first = sweep(cohort)
    assert first["processed"] == 0 and first["scan_truncated"] and first["next_scan_page"] == 11
    root.pages.clear()
    second = sweep(cohort)
    assert root.pages == [11] and second["processed"] == 1 and second["next_scan_page"] == 1


@pytest.mark.parametrize("cohort", [22], indirect=True)
def test_twenty_failures_cannot_starve_request_21_when_another_window_exists(cohort):
    root, *_ = cohort
    for number in range(1, 21):
        root.projects[f"student{number:02d}/project"].fail_secret_put = True
    # Window 1: twenty refused enrollments, valid enrollment21, then 979 PRs.
    # Window 2: valid enrollment22. Moving windows before finishing the first
    # one previously allowed the same first twenty failures to repeat forever.
    for number in range(10023, 11002):
        root.inbox[number] = {"id": number, "number": number, "state": "open", "pull_request": {}}
    root.inbox[22]["id"] = 20000
    first = sweep(cohort)
    assert first["failed"] == 20 and first["processed"] == 0
    assert first["next_scan_page"] == 1 and not first["window_complete"]
    second = sweep(cohort)
    assert second["processed"] == 1 and second["failed"] == 0 and second["next_scan_page"] == 11
    third = sweep(cohort)
    assert third["processed"] == 1 and third["failed"] == 0 and third["next_scan_page"] == 1
    assert {number for number, _ in root.comments} == {21, 22}


def test_request_receipt_signature_binds_immutable_issue_identity(cohort):
    root, *_ = cohort
    assert sweep(cohort)["processed"] == 1
    root.controller_variables["COCHEM_ACCESS_INBOX_ISSUE_10002"] = root.controller_variables["COCHEM_ACCESS_INBOX_ISSUE_10001"]
    with pytest.raises(controller.CourseAccessError, match="authenticated"):
        store_for(cohort).read("COCHEM_ACCESS_INBOX_ISSUE_10002")


def test_manual_sweep_requires_instructor_permission_and_no_project(cohort):
    _, config, api, *_ = cohort
    event = {"repository": {"private": True, "full_name": "Lab/Controller", "default_branch": "main",
                           "owner": {"type": "Organization"}}, "inputs": {"operation": "sweep"}}
    env = {"GITHUB_REPOSITORY": "Lab/Controller", "GITHUB_REF": "refs/heads/main",
           "GITHUB_SHA": "b" * 40, "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": "instructor"}
    assert controller.validate_event(event, env, config, api) == (None, "instructor", None)
    env["GITHUB_ACTOR"] = "student01"
    with pytest.raises(controller.CourseAccessError):
        controller.validate_event(event, env, config, api)


def test_workflow_keeps_single_writer_and_scheduled_durable_recovery():
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/course_project_access.yml").read_text()
    assert "group: cochem-project-access-${{ github.repository }}" in workflow
    assert "cancel-in-progress: false" in workflow
    assert "schedule:" in workflow and "cron: '7,22,37,52 * * * *'" in workflow
    assert "- sweep" in workflow and "default: sweep" in workflow
    assert "timeout-minutes: 10" in workflow
    assert "${{ github.event.issue.body }}" not in workflow
