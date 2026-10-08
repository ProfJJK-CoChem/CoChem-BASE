"""Real REST transport/cryptography engineering tests, never chemistry evidence.

A loopback protocol server accepts actual HTTP requests, verifies actual RSA JWT
signatures and decrypts actual libsodium sealed boxes. It is not GitHub-hosted
acceptance and generates no electronic-structure output.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import subprocess
import sys
import threading
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from nacl.exceptions import CryptoError
from nacl.public import PrivateKey, SealedBox

from cochem_base.interfaces.course_access import (
    ControllerConfig,
    CourseAccessError,
    EnrollmentRequest,
    GitHubAPI,
    app_jwt,
    encrypted_secret,
    enrollment_links,
    parse_enrollment,
    provision_project,
    verify_calculation_project,
)
from scripts import provision_student_project_access as controller_script


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class ProtocolServer(ThreadingHTTPServer):
    """An explicitly local engineering peer with distinct encryption stores."""

    def __init__(self):
        super().__init__(("127.0.0.1", 0), ProtocolHandler)
        self.signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.actions_key = PrivateKey.generate()
        self.codespaces_key = PrivateKey.generate()
        self.controller_token = secrets.token_urlsafe(32)
        self.error_secret = secrets.token_urlsafe(32)
        self.tokens = {}
        self.private = True
        self.controller_private = True
        self.active = True
        self.correct_installation = True
        self.source_changed = False
        self.tampered_path = ""
        self.starter_previous = False
        self.source_extra = False
        self.source_truncated = False
        self.excess_permissions = False
        self.fail_variable = False
        self.project_owner_type = "User"
        self.project_owner_login = "student"
        self.project_fork = False
        self.project_archived = False
        self.redirect = False
        self.authorized = []
        self.writes = []
        self.secret_values = {}
        self.codespaces_values = {}
        self.variables = {}
        self.critical = [
            {"path": "scripts/run_student_research.py", "sha": hashlib.sha1(b"worker-script").hexdigest(), "mode": "100644", "type": "blob"},
            {"path": ".github/workflows/student_research.yml", "sha": hashlib.sha1(b"workflow").hexdigest(), "mode": "100644", "type": "blob"},
            {"path": "pyproject.toml", "sha": hashlib.sha1(b"package").hexdigest(), "mode": "100644", "type": "blob"},
        ]
        for name in ("cli.py", "requirements-ui.txt", ".core_infrastructure_hashring.json",
                     "pytest.ini", "pytest-srs.ini", ".scripts/entry.sh", "Launch_CoChem_Mac.command"):
            self.critical.append({"path": name, "sha": hashlib.sha1(name.encode()).hexdigest(), "mode": "100644", "type": "blob"})

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_port}"


class ProtocolHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        # The controlled peer records structural requests, never Authorization.
        return None

    def do_GET(self):
        self.operation("GET")

    def do_POST(self):
        self.operation("POST")

    def do_PUT(self):
        self.operation("PUT")

    def do_PATCH(self):
        self.operation("PATCH")

    def answer(self, value, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if value is not None:
            self.wfile.write(json.dumps(value).encode())

    def operation(self, method):
        state = self.server
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"null")
        auth = self.headers.get("Authorization", "").removeprefix("Bearer ")
        path = self.path
        if path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", state.url + "/credential-destination")
            self.end_headers()
            return
        if path == "/credential-destination":
            state.authorized.append(auth)
            self.answer({})
            return
        if path == "/refused":
            self.answer({"message": state.error_secret}, 403)
            return
        if path in {"/orgs/Lab/installation", "/repos/student/project/installation"}:
            try:
                header, body, signature = auth.split(".")
                state.signing_key.public_key().verify(_decode(signature), (header + "." + body).encode(), padding.PKCS1v15(), hashes.SHA256())
                claims = json.loads(_decode(body))
                assert claims["iss"] == "123"
                assert claims["iat"] <= datetime.now(timezone.utc).timestamp() < claims["exp"]
            except Exception:
                self.answer({"message": "invalid RSA assertion"}, 401)
                return
            org = path.startswith("/orgs/")
            self.answer({"id": 11 if org else 22, "app_id": 123,
                         "repository_selection": "selected", "account": {
                         "login": "Lab" if org else ("student" if state.correct_installation else "other"),
                         "type": "Organization" if org else "User"}})
            return
        if path.startswith("/app/installations/") and path.endswith("/access_tokens"):
            token = secrets.token_urlsafe(32)
            state.tokens[token] = payload
            permissions = dict(payload["permissions"])
            if state.excess_permissions:
                permissions["administration"] = "write"
            self.answer({"token": token, "permissions": permissions,
                         "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=60)).isoformat()})
            return
        permissions = state.tokens.get(auth, {}).get("permissions", {})
        if path == "/repos/Lab/Controller":
            assert auth == state.controller_token
            self.answer({"private": state.controller_private, "full_name": "Lab/Controller", "owner": {"type": "Organization"}})
            return
        if path == "/repos/Lab/Controller/commits/main":
            self.answer({"sha": "b" * 40})
            return
        if path == "/repos/Lab/Controller/collaborators/instructor/permission":
            self.answer({"permission": "admin"})
            return
        if path == "/orgs/Lab/teams/research/memberships/student":
            assert permissions == {"members": "read"}
            self.answer({"state": "active" if state.active else "pending"})
            return
        if path == "/repos/student/project":
            if auth != state.controller_token:
                assert permissions == {"contents": "read"}
                assert state.tokens[auth]["repositories"] == ["project"]
            self.answer({"id": 42, "full_name": "student/project", "default_branch": "main", "private": state.private,
                         "archived": state.project_archived, "fork": state.project_fork,
                         "owner": {"login": state.project_owner_login, "type": state.project_owner_type}})
            return
        if path == "/repos/ProfJJK-CoChem/CoChem-BASE":
            self.answer({"id": 100, "full_name": "ProfJJK-CoChem/CoChem-BASE", "private": False,
                         "archived": False, "fork": False, "owner": {"login": "ProfJJK-CoChem", "type": "Organization"}})
            return
        if "/git/trees/" in path:
            tree = [dict(item) for item in state.critical]
            if state.starter_previous and path.startswith("/repos/Lab/BASE/git/trees/" + "a" * 40):
                tree[0]["sha"] = hashlib.sha1(b"new-approved-worker").hexdigest()
            if path.startswith("/repos/student/"):
                assert permissions == {"contents": "read"}
                if state.source_changed:
                    tree[0]["sha"] = "0" * 40
                for item in tree:
                    if item["path"] == state.tampered_path:
                        item["sha"] = hashlib.sha1(b"unapproved changed executable").hexdigest()
                if state.source_extra:
                    tree.append({"path": "scripts/extra.py", "sha": "d" * 40, "mode": "100644", "type": "blob"})
                tree.append({"path": "student-complex.xyz", "sha": "c" * 40, "mode": "100644", "type": "blob"})
            self.answer({"tree": tree, "truncated": state.source_truncated})
            return
        prefix = "/repos/student/project/"
        if path.startswith(prefix):
            assert state.tokens[auth]["repository_ids"] == [42]
            assert permissions == {"secrets": "write", "actions_variables": "write", "codespaces_secrets": "write"}
            if path.endswith("/secrets/public-key"):
                key = state.codespaces_key if "/codespaces/" in path else state.actions_key
                self.answer({"key_id": "public-key-id", "key": base64.b64encode(bytes(key.public_key)).decode()})
                return
            if method == "PUT" and "/secrets/" in path:
                assert set(payload) == {"encrypted_value", "key_id"}
                state.writes.append((method, path))
                key = state.codespaces_key if "/codespaces/" in path else state.actions_key
                value = SealedBox(key).decrypt(base64.b64decode(payload["encrypted_value"])).decode()
                target = state.codespaces_values if "/codespaces/" in path else state.secret_values
                target[path.rsplit("/", 1)[1]] = value
                self.answer(None, 201)
                return
            if "/actions/variables" in path:
                if state.fail_variable:
                    self.answer({"message": state.error_secret}, 403)
                    return
                if method == "GET":
                    name = path.rsplit("/", 1)[1]
                    self.answer({"name": name, "value": state.variables[name]} if name in state.variables else {}, 200 if name in state.variables else 404)
                else:
                    state.writes.append((method, path))
                    state.variables[payload["name"]] = payload["value"]
                    self.answer(None, 201 if method == "POST" else 204)
                return
        self.answer({"message": "unhandled engineering endpoint"}, 404)


@pytest.fixture
def peer():
    server = ProtocolServer()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        assert not worker.is_alive()


def config_for(peer, **changes):
    pem = peer.signing_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    config = ControllerConfig(repository="Lab/Controller", organization="Lab", team_slug="research", app_id="123",
        app_slug="cochem-research-access", approved_base_repository="Lab/BASE", approved_base_sha="a" * 40,
        private_key=pem, credentials={kind: secrets.token_urlsafe(32) for kind in ("orca", "cfour", "source")})
    return replace(config, **changes)


def provision(peer, config=None, enrollment=None, author="student"):
    config = config or config_for(peer)
    return provision_project(config, enrollment or EnrollmentRequest("student/project"), author=author,
        controller_api=GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True),
        app_api=GitHubAPI(app_jwt(config.app_id, config.private_key), api_url=peer.url, allow_loopback=True),
        authority_api=GitHubAPI(api_url=peer.url, allow_loopback=True))


def test_actual_http_provisions_encrypted_actions_and_codespaces_separately(peer):
    config = config_for(peer)
    receipt = provision(peer, config)
    assert receipt["status"] == "provisioned"
    assert receipt["available"] == ["cfour", "orca", "source"]
    assert receipt["codespaces_source"] == "available"
    assert len(peer.secret_values) == 3
    for kind in ("orca", "cfour", "source"):
        label = peer.variables[f"COCHEM_{kind.upper()}_ACCESS_SECRET"]
        assert label.startswith("COCHEM_ACCESS_")
        assert peer.secret_values[label] == config.credentials[kind]
        assert label not in json.dumps(receipt)
    assert peer.codespaces_values == {"COCHEM_SOURCE_CREDENTIAL": config.credentials["source"],
        "COCHEM_ACCESS_APP_SLUG": config.app_slug, "COCHEM_ACCESS_CONTROLLER_REPOSITORY": config.repository}
    assert all(value not in json.dumps(receipt) for value in config.credentials.values())
    assert config.private_key not in repr(config)
    assert peer.variables["COCHEM_APPROVED_BASE_SHA"] == config.approved_base_sha


def test_optional_engines_are_not_required_for_base_and_source_setup(peer):
    config = config_for(peer, credentials={"source": secrets.token_urlsafe(32)})
    receipt = provision(peer, config)
    assert receipt["available"] == ["source"]
    assert receipt["unavailable"] == ["cfour", "orca"]
    assert peer.variables["COCHEM_ORCA_ACCESS_SECRET"] == ""
    assert peer.variables["COCHEM_CFOUR_ACCESS_SECRET"] == ""


def test_no_licensed_engine_selection_leaves_only_requested_source(peer):
    receipt = provision(peer, enrollment=EnrollmentRequest("student/project", ()))
    assert receipt["available"] == ["source"]
    assert receipt["unavailable"] == []


def test_rotation_uses_new_private_labels_and_updates_existing_vars(peer):
    config = config_for(peer)
    provision(peer, config)
    old_labels = set(peer.secret_values)
    provision(peer, config)
    new_labels = set(peer.secret_values) - old_labels
    assert len(new_labels) == 3
    assert all(peer.variables[f"COCHEM_{kind.upper()}_ACCESS_SECRET"] in new_labels for kind in config.credentials)
    assert any(method == "PATCH" for method, path in peer.writes)


@pytest.mark.parametrize("flag", ["private", "controller_private", "active", "correct_installation"])
def test_ownership_membership_and_private_boundaries_refuse_before_writes(peer, flag):
    setattr(peer, flag, False)
    with pytest.raises(CourseAccessError):
        provision(peer)
    assert peer.writes == []


@pytest.mark.parametrize("flag", ["source_changed", "source_extra", "source_truncated", "excess_permissions"])
def test_source_tampering_and_broader_installation_permissions_refuse_before_writes(peer, flag):
    setattr(peer, flag, True)
    with pytest.raises(CourseAccessError):
        provision(peer)
    assert peer.writes == []


def test_another_students_repository_cannot_be_enrolled(peer):
    with pytest.raises(CourseAccessError, match="their own"):
        provision(peer, author="other")
    assert peer.writes == []


def test_instructor_approved_previous_starter_keeps_newest_worker_without_student_code(peer):
    peer.starter_previous = True
    config = config_for(peer, allowed_starter_shas=("d" * 40,))
    receipt = provision(peer, config)
    assert receipt["status"] == "provisioned"
    assert peer.variables["COCHEM_APPROVED_BASE_SHA"] == "a" * 40


def test_unapproved_previous_starter_is_not_silently_accepted(peer):
    peer.starter_previous = True
    with pytest.raises(CourseAccessError, match="starter"):
        provision(peer)
    assert peer.writes == []


@pytest.mark.parametrize("path", ["cli.py", "requirements-ui.txt", ".core_infrastructure_hashring.json",
    "pytest.ini", "pytest-srs.ini", ".scripts/entry.sh", "Launch_CoChem_Mac.command"])
def test_actual_bootstrap_and_build_control_blob_changes_refuse_private_readers(peer, path):
    peer.tampered_path = path
    with pytest.raises(CourseAccessError, match="starter"):
        provision(peer)
    assert peer.writes == []


def test_calculation_rechecks_actual_private_personal_repository(peer):
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    result = verify_calculation_project(api, "student/project")
    assert result["private"] is True
    assert result["canonical_maintainer"] is False
    assert result["repository_id"] == 42


def test_calculation_allows_only_explicit_canonical_public_maintainer(peer):
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    result = verify_calculation_project(api, "ProfJJK-CoChem/CoChem-BASE")
    assert result["private"] is False
    assert result["canonical_maintainer"] is True


@pytest.mark.parametrize("setting,value", [("private", False), ("project_owner_type", "Organization"),
    ("project_owner_login", "another"), ("project_fork", True), ("project_archived", True)])
def test_changed_visibility_or_personal_owner_stops_calculation_access(peer, setting, value):
    setattr(peer, setting, value)
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    with pytest.raises(CourseAccessError):
        verify_calculation_project(api, "student/project")
    assert peer.writes == []


def test_enrollment_cannot_establish_future_visibility_for_calculations(peer):
    assert provision(peer)["status"] == "provisioned"
    peer.private = False
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    with pytest.raises(CourseAccessError, match="private"):
        verify_calculation_project(api, "student/project")


@pytest.mark.parametrize("channel", ["main", "feature/course", ".cochem/course-channels/../bad.json"])
def test_course_channel_is_approval_data_and_never_a_branch_or_escape(peer, channel):
    with pytest.raises(CourseAccessError, match="channel"):
        config_for(peer, course_channel=channel)


def test_variable_failure_never_returns_ready_or_exposes_service_response(peer):
    peer.fail_variable = True
    with pytest.raises(CourseAccessError) as result:
        provision(peer)
    assert "HTTP 403" in str(result.value)
    assert peer.error_secret not in str(result.value)
    assert peer.variables == {}


def test_redirect_does_not_forward_authorization(peer):
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    with pytest.raises(CourseAccessError, match="not forwarded"):
        api.call("GET", "/redirect")
    assert peer.authorized == []


def test_rest_error_does_not_expose_secret_response_body(peer):
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    with pytest.raises(CourseAccessError) as result:
        api.call("GET", "/refused")
    assert peer.error_secret not in str(result.value)


@pytest.mark.parametrize("target", ["https://example.com", "http://api.github.com", "https://api.github.com.evil", "http://127.0.0.1:80/path"])
def test_no_arbitrary_endpoint_can_receive_credentials(target):
    with pytest.raises(CourseAccessError):
        GitHubAPI(secrets.token_urlsafe(20), api_url=target)


def test_actual_sealed_box_only_intended_recipient_can_decrypt():
    intended = PrivateKey.generate()
    other = PrivateKey.generate()
    value = secrets.token_urlsafe(32)
    ciphertext = encrypted_secret(base64.b64encode(bytes(intended.public_key)).decode(), value)
    assert SealedBox(intended).decrypt(base64.b64decode(ciphertext)).decode() == value
    with pytest.raises(CryptoError):
        SealedBox(other).decrypt(base64.b64decode(ciphertext))


def test_actual_rsa_jwt_signature_and_short_lifetime(peer):
    config = config_for(peer)
    token = app_jwt(config.app_id, config.private_key, now=1000)
    header, body, signature = token.split(".")
    peer.signing_key.public_key().verify(_decode(signature), (header + "." + body).encode(), padding.PKCS1v15(), hashes.SHA256())
    assert json.loads(_decode(header)) == {"alg": "RS256", "typ": "JWT"}
    assert json.loads(_decode(body)) == {"iat": 940, "exp": 1540, "iss": "123"}


@pytest.mark.parametrize("body", ["{}", "$(touch /tmp/no)", '{"schema":"wrong","repository":"student/project","engines":[]}',
    '{"schema":"cochem.student-project-access.v1","repository":"student/../project","engines":[]}',
    '{"schema":"cochem.student-project-access.v1","repository":"student/project","engines":["orca","orca"]}',
    '{"schema":"cochem.student-project-access.v1","repository":"student/project","engines":[[]]}', "x" * 2049])
def test_untrusted_enrollment_is_data_only_and_bounded(body):
    with pytest.raises(CourseAccessError):
        parse_enrollment(body)


def test_duplicate_json_enrollment_fields_are_rejected():
    body = '{"schema":"cochem.student-project-access.v1","repository":"student/project","repository":"student/other","engines":[]}'
    with pytest.raises(CourseAccessError, match="unique"):
        parse_enrollment(body)


def test_gui_links_roundtrip_exact_data_without_credentials():
    links = enrollment_links("Lab/Controller", "cochem-research-access", "student/project", ("orca",))
    assert links["install"] == "https://github.com/apps/cochem-research-access/installations/new"
    query = parse_qs(urlsplit(links["enroll"]).query)
    assert parse_enrollment(query["body"][0]) == EnrollmentRequest("student/project", ("orca",))


def test_issue_event_author_is_used_not_another_editor(peer):
    config = config_for(peer)
    event = {"repository": {"private": True, "full_name": "Lab/Controller", "default_branch": "main", "owner": {"type": "Organization"}},
             "action": "edited", "issue": {"number": 5, "user": {"login": "student"}, "body": json.dumps(EnrollmentRequest("student/project").to_dict())}}
    env = {"GITHUB_REPOSITORY": "Lab/Controller", "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "b" * 40, "GITHUB_EVENT_NAME": "issues", "GITHUB_ACTOR": "instructor"}
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    enrollment, author, number = controller_script.validate_event(event, env, config, api)
    assert author == "student" and enrollment.repository == "student/project" and number == 5
    event["issue"]["pull_request"] = {}
    with pytest.raises(controller_script.CourseAccessError):
        controller_script.validate_event(event, env, config, api)


def test_controller_workflow_has_private_default_branch_and_no_untrusted_shell_interpolation():
    source = (Path(__file__).resolve().parents[2] / ".github/workflows/course_project_access.yml").read_text()
    assert "github.event.repository.private == true" in source
    assert "github.repository == vars.COCHEM_ACCESS_CONTROLLER_REPOSITORY" in source
    assert "pull_request" not in source
    assert "${{ github.event.issue.body }}" not in source
    assert "persist-credentials: false" in source


def test_pure_enrollment_in_actual_empty_environment_requires_no_crypto(tmp_path):
    environment = tmp_path / "no-crypto-enrollment"
    created = subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(environment)],
                             capture_output=True, text=True, timeout=30)
    assert created.returncode == 0, created.stderr
    source = Path(__file__).resolve().parents[2] / "src/cochem_base/interfaces/course_access.py"
    python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    code = """import importlib.util,json,sys
assert importlib.util.find_spec('cryptography') is None
assert importlib.util.find_spec('nacl') is None
spec=importlib.util.spec_from_file_location('course_access_pure',sys.argv[1])
module=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=module
spec.loader.exec_module(module)
links=module.enrollment_links('Lab/Controller','lab-research','student/project',())
assert links['install']=='https://github.com/apps/lab-research/installations/new'
assert module.parse_enrollment(json.dumps(module.EnrollmentRequest('student/project',()).to_dict())).engines==()
print(json.dumps({'crypto_absent':True,'links_valid':True,'optional_engines':[]}))
"""
    actual = subprocess.run([str(python), "-I", "-B", "-c", code, str(source)],
                            capture_output=True, text=True, timeout=30)
    assert actual.returncode == 0, actual.stderr
    assert json.loads(actual.stdout) == {"crypto_absent": True, "links_valid": True, "optional_engines": []}


@pytest.mark.parametrize("change", ["public", "wrong_repository", "nondefault", "wrong_sha", "unsupported_event"])
def test_controller_event_source_authority_refuses_other_execution_routes(peer, change):
    config = config_for(peer)
    event = {"repository": {"private": True, "full_name": "Lab/Controller", "default_branch": "main", "owner": {"type": "Organization"}},
             "action": "opened", "issue": {"number": 5, "user": {"login": "student"}, "body": json.dumps(EnrollmentRequest("student/project").to_dict())}}
    env = {"GITHUB_REPOSITORY": "Lab/Controller", "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "b" * 40, "GITHUB_EVENT_NAME": "issues"}
    if change == "public":
        event["repository"]["private"] = False
    elif change == "wrong_repository":
        env["GITHUB_REPOSITORY"] = "student/project"
    elif change == "nondefault":
        env["GITHUB_REF"] = "refs/heads/student-branch"
    elif change == "wrong_sha":
        env["GITHUB_SHA"] = "d" * 40
    elif change == "unsupported_event":
        env["GITHUB_EVENT_NAME"] = "pull_request"
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    with pytest.raises(controller_script.CourseAccessError):
        controller_script.validate_event(event, env, config, api)
    assert peer.writes == []


def test_instructor_maintenance_dispatch_still_identifies_the_student_owner(peer):
    config = config_for(peer)
    event = {"repository": {"private": True, "full_name": "Lab/Controller", "default_branch": "main", "owner": {"type": "Organization"}},
             "inputs": {"project_repository": "student/project", "engines": "orca"}}
    env = {"GITHUB_REPOSITORY": "Lab/Controller", "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "b" * 40,
           "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": "instructor"}
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    enrollment, author, number = controller_script.validate_event(event, env, config, api)
    assert enrollment == controller_script.EnrollmentRequest("student/project", ("orca",))
    assert author == "student" and number is None
