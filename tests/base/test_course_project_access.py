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
import time
from dataclasses import dataclass, replace
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
    deprovision_project,
    encrypted_secret,
    enrollment_links,
    parse_enrollment,
    provision_project,
    reconcile_project,
    verify_calculation_project,
)
from scripts import provision_student_project_access as controller_script


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _blob_sha(value: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(value)).encode() + b"\0" + value).hexdigest()


@dataclass(frozen=True)
class ProtocolConfiguration:
    """Initial response data for the actual local HTTP engineering peer."""

    private: bool = True
    controller_private: bool = True
    active: bool = True
    correct_installation: bool = True
    source_changed: bool = False
    source_extra: bool = False
    source_truncated: bool = False
    excess_permissions: bool = False
    project_owner_type: str = "User"
    project_owner_login: str = "student"
    project_fork: bool = False
    project_archived: bool = False
    project_repository: str = "student/project"
    project_id: int = 42


class ProtocolServer(ThreadingHTTPServer):
    """An explicitly local engineering peer with distinct encryption stores."""

    def __init__(self, configuration: ProtocolConfiguration):
        super().__init__(("127.0.0.1", 0), ProtocolHandler)
        self.signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.actions_key = PrivateKey.generate()
        self.codespaces_key = PrivateKey.generate()
        self.controller_token = secrets.token_urlsafe(32)
        self.error_secret = secrets.token_urlsafe(32)
        self.tokens = {}
        self.private = configuration.private
        self.controller_private = configuration.controller_private
        self.active = configuration.active
        self.correct_installation = configuration.correct_installation
        self.source_changed = configuration.source_changed
        self.tampered_path = ""
        self.omit_project_path = ""
        self.extra_project_entries = []
        self.starter_previous = False
        self.source_extra = configuration.source_extra
        self.source_truncated = configuration.source_truncated
        self.excess_permissions = configuration.excess_permissions
        self.fail_variable = False
        self.fail_variable_name = ""
        self.fail_secret_put = False
        self.fail_delete = False
        self.installation_removed = False
        self.membership_missing = False
        self.reader_tokens = {}
        self.reader_requests = []
        self.reader_denied = False
        self.reader_delay = 0
        self.reader_wrong_tag = False
        self.reader_wrong_asset = False
        self.reader_wrong_digest = False
        self.reader_wrong_revision = False
        self.project_owner_type = configuration.project_owner_type
        self.project_owner_login = configuration.project_owner_login
        self.project_repository = configuration.project_repository
        self.project_id = configuration.project_id
        self.project_fork = configuration.project_fork
        self.project_archived = configuration.project_archived
        self.redirect = False
        self.authorized = []
        self.writes = []
        self.secret_values = {}
        self.codespaces_values = {}
        self.variables = {}
        self.controller_variables = {}
        self.ledger_denied = False
        self.devcontainer = (Path(__file__).resolve().parents[2] / ".devcontainer/devcontainer.json").read_bytes()
        self.project_devcontainer = self.devcontainer
        self.infrastructure_ring = (Path(__file__).resolve().parents[2] / ".core_infrastructure_hashring.json").read_bytes()
        self.project_ring = self.infrastructure_ring
        self.binding_failure = ""
        self.binding_readback = ""
        self.binding_committed = False
        self.project_revision = hashlib.sha1(b"original project commit").hexdigest()
        self.project_tree = hashlib.sha1(b"original project tree").hexdigest()
        self.git_blobs = {}
        self.git_trees = {}
        self.git_commits = {}
        self.deny_contents_write = False
        self.move_project_before_update = False
        self.critical = [
            {"path": "scripts/run_student_research.py", "sha": hashlib.sha1(b"worker-script").hexdigest(), "mode": "100644", "type": "blob"},
            {"path": ".github/workflows/student_research.yml", "sha": hashlib.sha1(b"workflow").hexdigest(), "mode": "100644", "type": "blob"},
            {"path": "pyproject.toml", "sha": hashlib.sha1(b"package").hexdigest(), "mode": "100644", "type": "blob"},
        ]
        for name in ("cli.py", "requirements-ui.txt", ".core_infrastructure_hashring.json",
                     "pytest.ini", "pytest-srs.ini", ".scripts/entry.sh", "Launch_CoChem_Mac.command"):
            self.critical.append({"path": name, "sha": hashlib.sha1(name.encode()).hexdigest(), "mode": "100644", "type": "blob"})
        self.critical.append({"path": ".devcontainer/devcontainer.json", "sha": _blob_sha(self.devcontainer),
                              "mode": "100644", "type": "blob"})
        for item in self.critical:
            if item["path"] == ".core_infrastructure_hashring.json":
                item["sha"] = _blob_sha(self.infrastructure_ring)

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

    def do_DELETE(self):
        self.operation("DELETE")

    def answer(self, value, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if value is not None:
            try:
                self.wfile.write(json.dumps(value).encode())
            except (BrokenPipeError, ConnectionResetError):
                return None

    def operation(self, method):
        state = self.server
        # A cohort peer can share controller/token authority while preserving
        # separate project secret stores and immutable repository identities.
        for project in getattr(state, "projects", {}).values():
            if (self.path == "/repos/" + project.project_repository
                    or self.path.startswith("/repos/" + project.project_repository + "/")
                    or self.path == "/orgs/Lab/teams/research/memberships/" + project.project_owner_login):
                state = project
                break
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
        for kind in ("orca", "cfour", "source"):
            repository = "Lab/Module" if kind == "source" else "Lab/" + kind.upper()
            prefix = "/repos/" + repository
            if path != prefix and not path.startswith(prefix + "/"):
                continue
            state.reader_requests.append((kind, path))
            if state.reader_delay:
                time.sleep(state.reader_delay)
            if state.reader_denied or state.reader_tokens.get(auth) != kind:
                self.answer({}, 403)
                return
            if path == prefix:
                self.answer({"full_name": repository, "private": True})
            elif kind == "source" and "/git/commits/" in path:
                self.answer({"sha": "0" * 40 if state.reader_wrong_revision else "f" * 40})
            elif kind == "source" and "/git/trees/" in path:
                self.answer({"tree": state.critical, "truncated": False})
            elif kind != "source" and path == prefix + "/releases/tags/reviewed-1":
                self.answer({"tag_name": "changed" if state.reader_wrong_tag else "reviewed-1", "draft": False,
                    "assets": [{"id": 61, "size": 4096, "state": "uploaded",
                        "name": "other.tar.xz" if state.reader_wrong_asset else "reviewed.tar.xz",
                        "digest": "sha256:" + ("0" * 64 if state.reader_wrong_digest else hashlib.sha256(b"protocol archive identity").hexdigest())}]})
            else:
                self.answer({}, 404)
            return
        if path in {"/orgs/Lab/installation", "/repos/" + state.project_repository + "/installation"}:
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
            if not org and state.installation_removed:
                self.answer({}, 404)
                return
            self.answer({"id": 11 if org else 22, "app_id": 123,
                         "repository_selection": "selected", "account": {
                         "login": "Lab" if org else (state.project_owner_login if state.correct_installation else "other"),
                         "type": "Organization" if org else "User"}})
            return
        if path.startswith("/app/installations/") and path.endswith("/access_tokens"):
            if state.deny_contents_write and payload["permissions"] == {"contents": "write"}:
                self.answer({"message": state.error_secret}, 422)
                return
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
        if path.startswith("/repos/Lab/Controller/actions/variables"):
            if (state.ledger_denied or permissions != {"actions_variables": "write"}
                    or state.tokens.get(auth, {}).get("repositories") != ["Controller"]):
                self.answer({}, 403)
                return
            if method == "GET":
                name = path.rsplit("/", 1)[1]
                self.answer({"name": name, "value": state.controller_variables[name]}
                            if name in state.controller_variables else {},
                            200 if name in state.controller_variables else 404)
            else:
                state.writes.append((method, path))
                state.controller_variables[payload["name"]] = payload["value"]
                self.answer(None, 201 if method == "POST" else 204)
            return
        if path == "/orgs/Lab/teams/research/memberships/" + state.project_owner_login:
            assert permissions == {"members": "read"}
            if state.membership_missing:
                self.answer({}, 404)
                return
            self.answer({"state": "active" if state.active else "pending"})
            return
        if path == "/repos/" + state.project_repository:
            if auth != state.controller_token:
                assert permissions == {"contents": "read"}
                assert state.tokens[auth]["repositories"] == [state.project_repository.split("/")[1]]
            identifier = state.project_id + 1 if state.binding_committed and state.binding_readback == "wrong_id" else state.project_id
            self.answer({"id": identifier, "full_name": state.project_repository, "default_branch": "main", "private": state.private,
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
            if path.startswith("/repos/" + state.project_repository + "/"):
                assert permissions == {"contents": "read"}
                if state.source_changed:
                    tree[0]["sha"] = "0" * 40
                for item in tree:
                    if item["path"] == ".devcontainer/devcontainer.json":
                        item["sha"] = _blob_sha(state.project_devcontainer)
                    if item["path"] == ".core_infrastructure_hashring.json":
                        item["sha"] = _blob_sha(state.infrastructure_ring if state.binding_committed
                            and state.binding_readback == "missing_ring" else state.project_ring)
                    if item["path"] == state.tampered_path:
                        item["sha"] = hashlib.sha1(b"unapproved changed executable").hexdigest()
                if state.source_extra:
                    tree.append({"path": "scripts/extra.py", "sha": "d" * 40, "mode": "100644", "type": "blob"})
                tree = [item for item in tree if item["path"] != state.omit_project_path]
                tree.extend(dict(item) for item in state.extra_project_entries)
                tree.append({"path": "student-complex.xyz", "sha": "c" * 40, "mode": "100644", "type": "blob"})
            self.answer({"tree": tree, "truncated": state.source_truncated})
            return
        if path.startswith("/repos/Lab/BASE/git/blobs/"):
            blobs = {_blob_sha(content): content for content in (state.devcontainer, state.infrastructure_ring)}
            content = blobs[path.rsplit("/", 1)[1]]
            self.answer({"sha": _blob_sha(content), "encoding": "base64",
                         "size": len(content), "content": base64.b64encode(content).decode()})
            return
        if path == "/repos/" + state.project_repository + "/git/ref/heads/main":
            assert permissions == {"contents": "read"}
            revision = "f" * 40 if state.binding_committed and state.binding_readback == "wrong_head" else state.project_revision
            self.answer({"object": {"type": "commit", "sha": revision}})
            return
        if path.startswith("/repos/" + state.project_repository + "/git/commits/") and method == "GET":
            assert permissions == {"contents": "read"}
            assert path.rsplit("/", 1)[1] == state.project_revision
            self.answer({"sha": state.project_revision, "tree": {"sha": state.project_tree}})
            return
        prefix = "/repos/" + state.project_repository + "/"
        if path.startswith(prefix):
            assert state.tokens[auth]["repository_ids"] == [state.project_id]
            if "/git/" in path:
                assert permissions == {"contents": "write"}
                state.writes.append((method, path))
                if path.endswith("/git/blobs") and method == "POST":
                    if state.binding_failure == "blob2" and state.git_blobs:
                        self.answer({}, 503)
                        return
                    assert payload["encoding"] == "base64"
                    content = base64.b64decode(payload["content"], validate=True)
                    digest = _blob_sha(content)
                    state.git_blobs[digest] = content
                    self.answer({"sha": digest}, 201)
                    return
                if path.endswith("/git/trees") and method == "POST":
                    if state.binding_failure == "tree":
                        self.answer({}, 503)
                        return
                    assert payload["base_tree"] == state.project_tree
                    assert len(payload["tree"]) == 2
                    assert {entry["path"] for entry in payload["tree"]} == {
                        ".devcontainer/devcontainer.json", ".core_infrastructure_hashring.json"}
                    assert all(entry["mode"] == "100644" and entry["type"] == "blob"
                               and entry["sha"] in state.git_blobs for entry in payload["tree"])
                    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                    state.git_trees[digest] = payload
                    self.answer({"sha": digest}, 201)
                    return
                if path.endswith("/git/commits") and method == "POST":
                    if state.binding_failure == "commit":
                        self.answer({}, 503)
                        return
                    assert payload["parents"] == [state.project_revision]
                    assert payload["tree"] in state.git_trees
                    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                    state.git_commits[digest] = payload
                    self.answer({"sha": digest}, 201)
                    return
                if path.endswith("/git/refs/heads/main") and method == "PATCH":
                    assert payload["force"] is False
                    if state.move_project_before_update or state.binding_failure == "ref":
                        self.answer({"message": "Reference update is not a fast-forward"}, 422)
                        return
                    commit = state.git_commits[payload["sha"]]
                    assert commit["parents"] == [state.project_revision]
                    tree = state.git_trees[commit["tree"]]
                    entries = {entry["path"]: entry["sha"] for entry in tree["tree"]}
                    state.project_devcontainer = state.git_blobs[entries[".devcontainer/devcontainer.json"]]
                    state.project_ring = state.git_blobs[entries[".core_infrastructure_hashring.json"]]
                    state.project_revision = payload["sha"]
                    state.project_tree = commit["tree"]
                    state.binding_committed = True
                    if state.binding_failure == "lost_ref_response":
                        self.answer({}, 503)
                        return
                    self.answer({"object": {"type": "commit", "sha": state.project_revision}})
                    return
            assert permissions == {"secrets": "write", "actions_variables": "write", "codespaces_secrets": "write"}
            if path.endswith("/secrets/public-key"):
                key = state.codespaces_key if "/codespaces/" in path else state.actions_key
                self.answer({"key_id": "public-key-id", "key": base64.b64encode(bytes(key.public_key)).decode()})
                return
            if method == "PUT" and "/secrets/" in path:
                if state.fail_secret_put:
                    self.answer({}, 403)
                    return
                assert set(payload) == {"encrypted_value", "key_id"}
                state.writes.append((method, path))
                key = state.codespaces_key if "/codespaces/" in path else state.actions_key
                value = SealedBox(key).decrypt(base64.b64decode(payload["encrypted_value"])).decode()
                target = state.codespaces_values if "/codespaces/" in path else state.secret_values
                target[path.rsplit("/", 1)[1]] = value
                self.answer(None, 201)
                return
            if "/secrets/" in path and method in {"GET", "DELETE"}:
                name = path.rsplit("/", 1)[1]
                target = state.codespaces_values if "/codespaces/" in path else state.secret_values
                if method == "DELETE":
                    state.writes.append((method, path))
                    if state.fail_delete:
                        self.answer({}, 403)
                        return
                    target.pop(name, None)
                    self.answer(None, 204)
                else:
                    self.answer({"name": name}, 200) if name in target else self.answer({}, 404)
                return
            if "/actions/variables" in path:
                if state.fail_variable or (method != "GET" and state.fail_variable_name == path.rsplit("/", 1)[1]):
                    self.answer({"message": state.error_secret}, 403)
                    return
                if method == "GET":
                    name = path.rsplit("/", 1)[1]
                    self.answer({"name": name, "value": state.variables[name]} if name in state.variables else {}, 200 if name in state.variables else 404)
                elif method == "DELETE":
                    state.writes.append((method, path))
                    state.variables.pop(path.rsplit("/", 1)[1], None)
                    self.answer(None, 204)
                else:
                    state.writes.append((method, path))
                    state.variables[payload["name"]] = payload["value"]
                    self.answer(None, 201 if method == "POST" else 204)
                return
        self.answer({"message": "unhandled engineering endpoint"}, 404)


@pytest.fixture
def peer(request):
    configuration = request.param if hasattr(request, "param") else ProtocolConfiguration()
    server = ProtocolServer(configuration)
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
        private_key=pem, credentials={kind: secrets.token_urlsafe(32) for kind in ("orca", "cfour", "source")},
        credential_targets={
            **{kind: {"repository": "Lab/" + kind.upper(), "release_tag": "reviewed-1",
                      "archive_name": "reviewed.tar.xz", "sha256": hashlib.sha256(b"protocol archive identity").hexdigest()}
               for kind in ("orca", "cfour")},
            "source": {"repository": "Lab/Module", "revision": "f" * 40}})
    config = replace(config, **changes)
    peer.reader_tokens.update({token: kind for kind, token in config.credentials.items()})
    return config


def provision(peer, config=None, enrollment=None, author="student"):
    config = config or config_for(peer)
    return provision_project(config, enrollment or EnrollmentRequest("student/project"), author=author,
        controller_api=GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True),
        app_api=GitHubAPI(app_jwt(config.app_id, config.private_key), api_url=peer.url, allow_loopback=True),
        authority_api=GitHubAPI(api_url=peer.url, allow_loopback=True))


def ownership_record(peer):
    return peer.controller_variables["COCHEM_ACCESS_PROJECT_42"]


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


def test_canonical_codespace_explicitly_authorizes_submission_to_its_own_project():
    path = Path(__file__).resolve().parents[2] / ".devcontainer/devcontainer.json"
    repositories = json.loads(path.read_bytes())["customizations"]["codespaces"]["repositories"]
    assert repositories["ProfJJK-CoChem/CoChem-BASE"]["permissions"] == {
        "actions": "write", "contents": "write"}
    assert all(value["permissions"] == {"contents": "read"}
               for name, value in repositories.items() if name != "ProfJJK-CoChem/CoChem-BASE")


def test_enrollment_prepares_exact_project_permissions_without_changing_launch_code(peer):
    receipt = provision(peer)
    original = json.loads(peer.devcontainer)
    actual = json.loads(peer.project_devcontainer)
    assert actual["customizations"]["codespaces"]["repositories"] == {
        "student/project": {"permissions": {"actions": "write", "contents": "write"}}}
    original["customizations"]["codespaces"]["repositories"] = actual["customizations"]["codespaces"]["repositories"]
    assert actual == original
    assert receipt["codespaces_configuration_sha"] == _blob_sha(peer.project_devcontainer)
    assert receipt["codespaces_ring_sha"] == _blob_sha(peer.project_ring)
    assert receipt["codespaces_binding_schema"] == "cochem.codespaces-project-binding/2"
    assert receipt["source_state"] == "paired"
    ring = json.loads(peer.project_ring)
    assert ring["files"][".devcontainer/devcontainer.json"] == hashlib.sha256(peer.project_devcontainer).hexdigest()
    ring["files"][".devcontainer/devcontainer.json"] = hashlib.sha256(peer.devcontainer).hexdigest()
    assert ring == json.loads(peer.infrastructure_ring)
    assert receipt["codespaces_authorization_required"] is True
    assert len(peer.git_commits) == 1
    assert all(request.get("repository_ids") == [42] for request in peer.tokens.values()
               if request["permissions"] == {"contents": "write"})
    previous = peer.project_revision
    provision(peer)
    assert peer.project_revision == previous
    assert len(peer.git_commits) == 1


@pytest.mark.parametrize("change", ["other_project", "broad_grant", "extra_permission", "startup_command", "environment", "formatting"])
def test_only_exact_generated_codespace_configuration_is_accepted(peer, change):
    provision(peer)
    actual = json.loads(peer.project_devcontainer)
    if change == "other_project":
        actual["customizations"]["codespaces"]["repositories"] = {"student/other": {"permissions": {"actions": "write", "contents": "write"}}}
    elif change == "broad_grant":
        actual["customizations"]["codespaces"]["repositories"] = {"student/*": {"permissions": "write-all"}}
    elif change == "extra_permission":
        actual["customizations"]["codespaces"]["repositories"]["student/project"]["permissions"]["workflows"] = "write"
    elif change == "startup_command":
        actual["postCreateCommand"] = "python unapproved.py"
    elif change == "environment":
        actual["containerEnv"]["UNAPPROVED"] = "1"
    peer.project_devcontainer = json.dumps(actual, indent=None if change == "formatting" else 2).encode() + b"\n"
    peer.writes.clear()
    with pytest.raises(CourseAccessError, match="starter"):
        provision(peer)
    assert peer.writes == []


def test_missing_app_contents_write_reports_instructor_action_before_credentials(peer):
    peer.deny_contents_write = True
    with pytest.raises(CourseAccessError, match="Contents.*Read and write") as result:
        provision(peer)
    assert peer.error_secret not in str(result.value)
    assert peer.secret_values == {} and peer.codespaces_values == {}
    assert peer.writes == []


def test_concurrent_project_change_is_not_overwritten_or_given_credentials(peer):
    peer.move_project_before_update = True
    original = peer.project_revision
    with pytest.raises(CourseAccessError, match="changed|update"):
        provision(peer)
    assert peer.project_revision == original
    assert peer.project_devcontainer == peer.devcontainer
    assert peer.secret_values == {} and peer.codespaces_values == {}


def test_optional_engines_are_not_required_for_base_and_source_setup(peer):
    config = config_for(peer, credentials={"source": secrets.token_urlsafe(32)})
    receipt = provision(peer, config)
    assert receipt["available"] == ["source"]
    assert receipt["unavailable"] == ["cfour", "orca"]
    assert peer.variables["COCHEM_ORCA_ACCESS_SECRET"] == ""
    assert peer.variables["COCHEM_CFOUR_ACCESS_SECRET"] == ""


@pytest.mark.parametrize("private_source", [False, True])
def test_enrollment_message_keeps_public_modules_available_without_certifying_installation(peer, private_source):
    credentials = {"source": secrets.token_urlsafe(32)} if private_source else {}
    receipt = provision(peer, config_for(peer, credentials=credentials))
    comment = controller_script.enrollment_comment(receipt)
    assert "Public TOPOS/TORQ source downloads do not require a private source credential" in comment
    assert "Module installation has not been verified" in comment
    assert "TOPOS/TORQ downloads are not connected" not in comment
    assert "**new Codespace**" in comment
    assert receipt["module_installation_performed"] is False
    assert receipt["engine_execution_performed"] is False
    assert receipt["codespaces_source"] == ("available" if private_source else "unavailable")
    assert ("private module downloads" in comment) is private_source
    assert peer.codespaces_values.get("COCHEM_SOURCE_CREDENTIAL", "") == credentials.get("source", "")
    assert all(value not in comment for value in credentials.values())


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
    assert not old_labels.intersection(peer.secret_values)


@pytest.mark.parametrize("peer", [ProtocolConfiguration(private=False), ProtocolConfiguration(controller_private=False),
    ProtocolConfiguration(active=False), ProtocolConfiguration(correct_installation=False)], indirect=True)
def test_ownership_membership_and_private_boundaries_refuse_before_writes(peer):
    with pytest.raises(CourseAccessError):
        provision(peer)
    assert peer.writes == []


@pytest.mark.parametrize("peer", [ProtocolConfiguration(source_changed=True), ProtocolConfiguration(source_extra=True),
    ProtocolConfiguration(source_truncated=True), ProtocolConfiguration(excess_permissions=True)], indirect=True)
def test_source_tampering_and_broader_installation_permissions_refuse_before_writes(peer):
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


@pytest.mark.parametrize("case", ["correct_new", "missing_new", "tampered_new", "valid_old", "unexpected_old"])
def test_admission_descriptor_source_identity_is_required_only_when_approved(peer, case):
    """Real HTTP tree checks prove source identity, not descriptor semantics or hosted enrollment."""
    path = ".cochem/student-actions-admission.json"
    raw = json.dumps({"schema_version": "engineering.source-identity/1",
                      "purpose": "Descriptor path membership control; no execution authority"}).encode()
    entry = {"path": path, "sha": _blob_sha(raw), "mode": "100644", "type": "blob"}
    if case.endswith("new"):
        peer.critical.append(entry)
    if case == "missing_new":
        peer.omit_project_path = path
    elif case == "tampered_new":
        peer.tampered_path = path
    elif case == "unexpected_old":
        peer.extra_project_entries.append(entry)
    # An unrelated student data record must not turn into protected executable
    # source merely because it shares the .cochem directory with the descriptor.
    peer.extra_project_entries.append({"path": ".cochem/student-notes.json",
        "sha": _blob_sha(b'{"note":"Independent student data, not admission authority"}\n'),
        "mode": "100644", "type": "blob"})
    if case in {"correct_new", "valid_old"}:
        receipt = provision(peer)
        assert receipt["status"] == "provisioned"
        assert receipt["starter_sha"] == "a" * 40
    else:
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


@pytest.mark.parametrize("peer", [ProtocolConfiguration(private=False), ProtocolConfiguration(project_owner_type="Organization"),
    ProtocolConfiguration(project_owner_login="another"), ProtocolConfiguration(project_fork=True),
    ProtocolConfiguration(project_archived=True)], indirect=True)
def test_changed_visibility_or_personal_owner_stops_calculation_access(peer):
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


def lifecycle(peer, operation, config=None, enrollment=None):
    config = config or config_for(peer)
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    app_api = GitHubAPI(app_jwt(config.app_id, config.private_key), api_url=peer.url, allow_loopback=True)
    if operation == "deprovision":
        return deprovision_project(config, "student/project", controller_api=api, app_api=app_api)
    return reconcile_project(config, enrollment or EnrollmentRequest("student/project"),
        controller_api=api, app_api=app_api, authority_api=GitHubAPI(api_url=peer.url, allow_loopback=True))


def test_selected_engine_withdrawal_deletes_only_authenticated_owned_secrets(peer):
    config = config_for(peer)
    provision(peer, config)
    old_orca = peer.variables["COCHEM_ORCA_ACCESS_SECRET"]
    peer.secret_values["STUDENT_OTHER_SECRET"] = secrets.token_urlsafe(32)
    peer.secret_values["COCHEM_ACCESS_" + "F" * 32] = secrets.token_urlsafe(32)
    peer.codespaces_values["STUDENT_OTHER_SECRET"] = secrets.token_urlsafe(32)
    unrelated = {name: value for name, value in peer.secret_values.items()
                 if name in {"STUDENT_OTHER_SECRET", "COCHEM_ACCESS_" + "F" * 32}}
    receipt = provision(peer, config, EnrollmentRequest("student/project", ("cfour",)))
    assert peer.variables["COCHEM_ORCA_ACCESS_SECRET"] == ""
    assert old_orca not in peer.secret_values
    assert all(peer.secret_values[name] == value for name, value in unrelated.items())
    assert "STUDENT_OTHER_SECRET" in peer.codespaces_values
    assert receipt["available"] == ["cfour", "source"]
    assert receipt["cleanup_pending"] == 0
    assert receipt["credential_values_revoked"] is False
    assert receipt["current_job_authorization_enforced"] is False


def test_replacement_failure_preserves_previous_bindings_and_owned_retry_record(peer):
    config = config_for(peer)
    provision(peer, config)
    previous = {name: value for name, value in peer.variables.items() if name != "COCHEM_ACCESS_OWNERSHIP"}
    old_secrets = dict(peer.secret_values)
    peer.fail_secret_put = True
    with pytest.raises(CourseAccessError):
        provision(peer, config)
    assert all(peer.variables[name] == value for name, value in previous.items())
    assert peer.secret_values == old_secrets
    assert json.loads(ownership_record(peer))["payload"]["state"] == "staging"
    peer.fail_secret_put = False
    assert provision(peer, config)["status"] == "provisioned"
    assert len(peer.secret_values) == 3
    assert not old_secrets.keys() & peer.secret_values.keys()


def test_binding_failure_restores_previous_settings_before_retiring_any_reader(peer):
    config = config_for(peer)
    provision(peer, config)
    previous = {name: value for name, value in peer.variables.items() if name != "COCHEM_ACCESS_OWNERSHIP"}
    old_secrets = dict(peer.secret_values)
    peer.fail_variable_name = "COCHEM_CFOUR_ACCESS_SECRET"
    with pytest.raises(CourseAccessError, match="incomplete"):
        provision(peer, config)
    assert all(peer.variables[name] == value for name, value in previous.items())
    assert all(peer.secret_values[name] == value for name, value in old_secrets.items())
    peer.fail_variable_name = ""
    assert provision(peer, config)["status"] == "provisioned"
    assert len(peer.secret_values) == 3


def test_failed_old_label_cleanup_is_recorded_and_retried(peer):
    config = config_for(peer)
    provision(peer, config)
    old = set(peer.secret_values)
    peer.fail_delete = True
    receipt = provision(peer, config)
    assert receipt["status"] == "cleanup_pending" and receipt["cleanup_pending"] == 3
    assert old <= peer.secret_values.keys()
    owned = json.loads(ownership_record(peer))["payload"]
    assert old <= set(owned["actions"])
    peer.fail_delete = False
    assert lifecycle(peer, "reconcile", config)["status"] == "provisioned"
    assert not old.intersection(peer.secret_values)
    assert len(peer.secret_values) == 3


def test_source_withdrawal_removes_its_owned_codespaces_secret(peer):
    config = config_for(peer)
    provision(peer, config)
    receipt = provision(peer, replace(config, credentials={"orca": config.credentials["orca"]}),
                        EnrollmentRequest("student/project", ("orca",)))
    assert "COCHEM_SOURCE_CREDENTIAL" not in peer.codespaces_values
    assert peer.variables["COCHEM_SOURCE_ACCESS_SECRET"] == ""
    assert receipt["codespaces_source"] == "unavailable"
    assert len(peer.secret_values) == 1


@pytest.mark.parametrize("change", ["labels", "project_id", "signature", "duplicate"])
def test_corrupted_trusted_ownership_never_authorizes_deletion(peer, change):
    config = config_for(peer)
    provision(peer, config)
    document = json.loads(ownership_record(peer))
    if change == "labels":
        document["payload"]["actions"].append("COCHEM_ACCESS_" + "F" * 32)
    elif change == "project_id":
        document["payload"]["repository_id"] = 99
    elif change == "signature":
        document["signature"] = base64.b64encode(secrets.token_bytes(256)).decode()
    peer.controller_variables["COCHEM_ACCESS_PROJECT_42"] = json.dumps(document)
    if change == "duplicate":
        peer.controller_variables["COCHEM_ACCESS_PROJECT_42"] = '{"payload":{},' + ownership_record(peer)[1:]
    previous = dict(peer.secret_values)
    peer.writes.clear()
    with pytest.raises(CourseAccessError, match="authenticated"):
        lifecycle(peer, "deprovision", config)
    assert peer.writes == []
    assert peer.secret_values == previous


def test_unsigned_existing_access_settings_are_preserved_for_instructor_migration(peer):
    peer.variables["COCHEM_ORCA_ACCESS_SECRET"] = "STUDENT_EXISTING_SECRET"
    peer.secret_values["STUDENT_EXISTING_SECRET"] = secrets.token_urlsafe(32)
    previous = dict(peer.secret_values)
    with pytest.raises(CourseAccessError, match="ownership"):
        provision(peer)
    assert peer.secret_values == previous
    assert peer.variables == {"COCHEM_ORCA_ACCESS_SECRET": "STUDENT_EXISTING_SECRET"}
    assert peer.writes == []


def test_unsigned_existing_codespaces_setting_is_never_overwritten(peer):
    peer.codespaces_values["COCHEM_SOURCE_CREDENTIAL"] = secrets.token_urlsafe(32)
    previous = dict(peer.codespaces_values)
    with pytest.raises(CourseAccessError, match="ownership"):
        provision(peer)
    assert peer.codespaces_values == previous
    assert peer.writes == []


def test_deprovision_after_membership_and_visibility_change_preserves_project_files(peer):
    config = config_for(peer)
    provision(peer, config)
    peer.active = False
    peer.private = False
    peer.source_changed = True
    peer.secret_values["STUDENT_SECRET"] = secrets.token_urlsafe(32)
    peer.codespaces_values["STUDENT_SECRET"] = secrets.token_urlsafe(32)
    peer.variables["STUDENT_SETTING"] = "preserve"
    original = (peer.project_revision, peer.project_devcontainer)
    receipt = lifecycle(peer, "reconcile", config)
    assert receipt["status"] == "deprovisioned"
    assert peer.secret_values.keys() == {"STUDENT_SECRET"}
    assert peer.codespaces_values.keys() == {"STUDENT_SECRET"}
    assert peer.variables["STUDENT_SETTING"] == "preserve"
    assert all(peer.variables[name] == "" for name in (
        "COCHEM_ORCA_ACCESS_SECRET", "COCHEM_CFOUR_ACCESS_SECRET", "COCHEM_SOURCE_ACCESS_SECRET",
        "COCHEM_APPROVED_BASE_SHA", "COCHEM_COURSE_CHANNEL"))
    assert (peer.project_revision, peer.project_devcontainer) == original
    assert receipt["credential_values_revoked"] is False
    assert lifecycle(peer, "deprovision", config)["status"] == "deprovisioned"


def test_missing_team_membership_reconciles_to_withdrawal_and_allows_reenrollment(peer):
    config = config_for(peer)
    provision(peer, config)
    peer.membership_missing = True
    assert lifecycle(peer, "reconcile", config)["status"] == "deprovisioned"
    assert peer.secret_values == {} and peer.codespaces_values == {}
    peer.membership_missing = False
    assert lifecycle(peer, "reconcile", config)["status"] == "provisioned"
    assert len(peer.secret_values) == 3


def test_app_uninstall_is_an_explicit_cleanup_blocker_never_success(peer):
    config = config_for(peer)
    provision(peer, config)
    previous = (dict(peer.secret_values), dict(peer.codespaces_values), dict(peer.variables))
    peer.installation_removed = True
    peer.writes.clear()
    with pytest.raises(CourseAccessError, match="HTTP 404"):
        lifecycle(peer, "deprovision", config)
    assert (peer.secret_values, peer.codespaces_values, peer.variables) == previous
    assert peer.writes == []


def test_partial_deprovision_retains_owned_cleanup_record_and_reenrollment(peer):
    config = config_for(peer)
    provision(peer, config)
    peer.fail_delete = True
    receipt = lifecycle(peer, "deprovision", config)
    assert receipt["status"] == "cleanup_pending" and receipt["cleanup_pending"] == 6
    assert peer.variables["COCHEM_ORCA_ACCESS_SECRET"] == ""
    peer.fail_delete = False
    assert lifecycle(peer, "deprovision", config)["status"] == "deprovisioned"
    assert peer.secret_values == {} and peer.codespaces_values == {}
    assert provision(peer, config)["status"] == "provisioned"
    assert len(peer.secret_values) == 3


@pytest.mark.parametrize("operation", ["provision", "reconcile", "deprovision"])
def test_instructor_lifecycle_dispatch_uses_existing_authority_checks(peer, operation):
    config = config_for(peer)
    event = {"repository": {"private": True, "full_name": "Lab/Controller", "default_branch": "main", "owner": {"type": "Organization"}},
             "inputs": {"project_repository": "student/project", "engines": "orca", "operation": operation}}
    env = {"GITHUB_REPOSITORY": "Lab/Controller", "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "b" * 40,
           "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": "instructor"}
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    enrollment, author, issue = controller_script.validate_event(event, env, config, api)
    assert enrollment.repository == "student/project" and author == "student" and issue is None
    assert peer.writes == []


@pytest.mark.parametrize("operation", ["shell", [], None])
def test_instructor_lifecycle_dispatch_rejects_unsupported_operations(peer, operation):
    config = config_for(peer)
    event = {"repository": {"private": True, "full_name": "Lab/Controller", "default_branch": "main", "owner": {"type": "Organization"}},
             "inputs": {"project_repository": "student/project", "operation": operation}}
    env = {"GITHUB_REPOSITORY": "Lab/Controller", "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "b" * 40,
           "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_ACTOR": "instructor"}
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    with pytest.raises(controller_script.CourseAccessError, match="lifecycle"):
        controller_script.validate_event(event, env, config, api)
    assert peer.writes == []


@pytest.mark.parametrize("failure", ["denied", "wrong_tag", "wrong_asset", "wrong_digest", "wrong_revision"])
def test_replacement_reader_failure_preserves_working_credentials_and_every_setting(peer, failure):
    config = config_for(peer)
    provision(peer, config)
    previous = (dict(peer.secret_values), dict(peer.codespaces_values), dict(peer.variables),
                peer.project_revision, peer.project_devcontainer)
    if failure == "denied":
        peer.reader_denied = True
    elif failure == "wrong_tag":
        peer.reader_wrong_tag = True
    elif failure == "wrong_asset":
        peer.reader_wrong_asset = True
    elif failure == "wrong_digest":
        peer.reader_wrong_digest = True
    elif failure == "wrong_revision":
        peer.reader_wrong_revision = True
    peer.writes.clear()
    with pytest.raises(CourseAccessError):
        provision(peer, config)
    assert (peer.secret_values, peer.codespaces_values, peer.variables,
            peer.project_revision, peer.project_devcontainer) == previous
    assert peer.writes == []


def test_actual_reader_transport_timeout_preserves_working_credentials(peer):
    config = config_for(peer)
    provision(peer, config)
    previous = (dict(peer.secret_values), dict(peer.codespaces_values), dict(peer.variables))
    peer.reader_delay = 0.5
    peer.reader_requests.clear()
    peer.writes.clear()
    with pytest.raises(CourseAccessError, match="connectivity"):
        provision_project(config, EnrollmentRequest("student/project"), author="student",
            controller_api=GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True),
            app_api=GitHubAPI(app_jwt(config.app_id, config.private_key), api_url=peer.url,
                              allow_loopback=True, timeout_seconds=0.2),
            authority_api=GitHubAPI(api_url=peer.url, allow_loopback=True))
    assert (peer.secret_values, peer.codespaces_values, peer.variables) == previous
    assert peer.writes == []
    assert peer.reader_requests and peer.reader_requests[0][0] == "orca"


def test_missing_reviewed_source_target_preserves_working_access(peer):
    config = config_for(peer)
    provision(peer, config)
    previous = (dict(peer.secret_values), dict(peer.codespaces_values), dict(peer.variables))
    targets = {name: value for name, value in config.credential_targets.items() if name != "source"}
    with pytest.raises(CourseAccessError, match="reviewed immutable"):
        provision(peer, replace(config, credential_targets=targets))
    assert (peer.secret_values, peer.codespaces_values, peer.variables) == previous
    assert lifecycle(peer, "deprovision", replace(config, credential_targets={}))['status'] == 'deprovisioned'


def test_actual_metadata_probe_never_claims_download_or_engine_execution(peer):
    receipt = provision(peer)
    assert receipt["reader_metadata_verified"] == ["cfour", "orca", "source"]
    assert receipt["asset_download_verified"] is False
    assert receipt["engine_access_verified"] is False
    assert receipt["engine_execution_performed"] is False


def test_controller_reader_targets_come_from_its_reviewed_manifests_not_enrollment():
    credentials = {kind: secrets.token_urlsafe(32) for kind in ("orca", "cfour", "source")}
    targets = controller_script.credential_targets({}, credentials)
    root = Path(__file__).resolve().parents[2]
    for engine in ("orca", "cfour"):
        manifest = json.loads((root / "scripts" / (engine + "-distribution.json")).read_text())
        assert targets[engine] == {name: manifest[name] for name in (
            "repository", "release_tag", "archive_name", "sha256")}
    assert "source" not in targets
    configured = controller_script.credential_targets({"COCHEM_ACCESS_SOURCE_REPOSITORY": "Lab/Module",
        "COCHEM_ACCESS_SOURCE_REVISION": "f" * 40}, credentials)
    assert configured["source"] == {"repository": "Lab/Module", "revision": "f" * 40}


@pytest.mark.parametrize("student_record", ["legacy", "same_name", "deleted"])
def test_student_ownership_replay_or_deletion_cannot_hide_current_generation(peer, student_record):
    config = config_for(peer)
    provision(peer, config)
    historical = ownership_record(peer)
    first = set(peer.secret_values)
    provision(peer, config)
    current = set(peer.secret_values)
    assert len(current) == 3 and not first.intersection(current)
    if student_record == "legacy":
        peer.variables["COCHEM_ACCESS_OWNERSHIP"] = historical
    elif student_record == "same_name":
        peer.variables["COCHEM_ACCESS_PROJECT_42"] = historical
    else:
        peer.variables["COCHEM_ACCESS_OWNERSHIP"] = historical
        del peer.variables["COCHEM_ACCESS_OWNERSHIP"]
    peer.secret_values["STUDENT_SECRET"] = secrets.token_urlsafe(32)
    receipt = lifecycle(peer, "deprovision", config)
    assert receipt["status"] == "deprovisioned" and receipt["cleanup_pending"] == 0
    assert not current.intersection(peer.secret_values)
    assert set(peer.secret_values) == {"STUDENT_SECRET"}
    assert peer.codespaces_values == {}
    latest = json.loads(ownership_record(peer))["payload"]
    assert latest["actions"] == [] and latest["bindings"] == {} and latest["state"] == "revoked"


@pytest.mark.parametrize("clear_student_selector", [False, True])
def test_requested_but_missing_replacement_reader_preserves_all_existing_access(peer, clear_student_selector):
    config = config_for(peer)
    provision(peer, config)
    if clear_student_selector:
        peer.variables["COCHEM_ORCA_ACCESS_SECRET"] = ""
    previous = (dict(peer.secret_values), dict(peer.codespaces_values), dict(peer.variables),
                dict(peer.controller_variables), peer.project_revision)
    unavailable = replace(config, credentials={kind: value for kind, value in config.credentials.items()
                                               if kind != "orca"})
    peer.writes.clear()
    with pytest.raises(CourseAccessError, match="still-requested"):
        provision(peer, unavailable)
    assert (peer.secret_values, peer.codespaces_values, peer.variables,
            peer.controller_variables, peer.project_revision) == previous
    assert peer.writes == []
    # Actual deselection is a withdrawal, even while the controller reader is absent.
    receipt = provision(peer, unavailable, EnrollmentRequest("student/project", ("cfour",)))
    assert receipt["status"] == "provisioned"
    assert peer.variables["COCHEM_ORCA_ACCESS_SECRET"] == ""
    assert len(peer.secret_values) == 2


def test_private_ledger_access_denial_preserves_existing_access(peer):
    config = config_for(peer)
    provision(peer, config)
    previous = (dict(peer.secret_values), dict(peer.codespaces_values), dict(peer.variables),
                dict(peer.controller_variables))
    peer.ledger_denied = True
    peer.writes.clear()
    with pytest.raises(CourseAccessError, match="HTTP 403"):
        lifecycle(peer, "deprovision", config)
    assert (peer.secret_values, peer.codespaces_values, peer.variables, peer.controller_variables) == previous
    assert peer.writes == []


def test_project_scoped_writer_cannot_modify_authoritative_controller_ledger(peer):
    config = config_for(peer)
    provision(peer, config)
    trusted = dict(peer.controller_variables)
    project_token = next(token for token, grant in peer.tokens.items()
        if grant["permissions"] == {"secrets": "write", "actions_variables": "write", "codespaces_secrets": "write"})
    api = GitHubAPI(project_token, api_url=peer.url, allow_loopback=True)
    with pytest.raises(CourseAccessError, match="HTTP 403"):
        api.call("PATCH", "/repos/Lab/Controller/actions/variables/COCHEM_ACCESS_PROJECT_42",
                 {"name": "COCHEM_ACCESS_PROJECT_42", "value": "historical or attacker data"})
    assert peer.controller_variables == trusted


def test_all_enrollment_and_maintenance_runs_share_one_serialized_controller_group():
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/course_project_access.yml").read_text()
    # GitHub variables provide no compare-and-swap. The complete workflow,
    # including distinct issue events and manual maintenance, must share this
    # repository-wide group. No issue/run/project input may narrow that boundary.
    start = workflow.index("\nconcurrency:\n")
    concurrency = workflow[start:workflow.index("\njobs:", start)]
    assert "group: cochem-project-access-${{ github.repository }}" in concurrency
    assert "cancel-in-progress: false" in concurrency
    assert "github.event.issue" not in concurrency and "github.run_id" not in concurrency
    assert "inputs." not in concurrency


def test_missing_requested_reader_preserves_interrupted_initial_generation(peer):
    config = config_for(peer)
    peer.fail_secret_put = True
    with pytest.raises(CourseAccessError):
        provision(peer, config)
    initial = json.loads(ownership_record(peer))["payload"]
    assert initial["state"] == "staging" and initial["bindings"]["orca"] in initial["actions"]
    before = (dict(peer.variables), dict(peer.controller_variables), dict(peer.secret_values))
    peer.fail_secret_put = False
    absent = replace(config, credentials={kind: value for kind, value in config.credentials.items() if kind != "orca"})
    peer.writes.clear()
    with pytest.raises(CourseAccessError, match="still-requested"):
        provision(peer, absent)
    assert (peer.variables, peer.controller_variables, peer.secret_values) == before
    assert peer.writes == []
    assert lifecycle(peer, "deprovision", absent)["status"] == "deprovisioned"


def test_colab_binding_variable_and_sync_calculation_access(peer):
    from cochem_base.interfaces.course_access import BINDING_VARIABLES, sync_calculation_access
    assert BINDING_VARIABLES["colab"] == "COCHEM_COLAB_ACCESS_SECRET"
    colab_token = secrets.token_urlsafe(32)
    config = config_for(peer)
    config_colab = replace(config, credentials={**config.credentials, "colab": colab_token})
    receipt = provision(peer, config_colab)
    assert receipt["status"] == "provisioned" and "colab" in receipt["available"]
    label = peer.variables["COCHEM_COLAB_ACCESS_SECRET"]
    assert label.startswith("COCHEM_ACCESS_") and label != "COLAB_OFFLOAD_DISPATCH_TOKEN"
    assert peer.secret_values[label] == colab_token
    assert peer.codespaces_values["COLAB_OFFLOAD_DISPATCH_TOKEN"] == colab_token
    assert "colab" not in receipt["reader_metadata_verified"]
    assert receipt["colab_access_verified"] is False
    api = GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True)
    app_api = GitHubAPI(app_jwt(config_colab.app_id, config_colab.private_key), api_url=peer.url, allow_loopback=True)
    sync_receipt = sync_calculation_access(config_colab,
        EnrollmentRequest("student/project", ("orca", "cfour")), author="student",
        controller_api=api, app_api=app_api,
        authority_api=GitHubAPI(api_url=peer.url, allow_loopback=True))
    assert sync_receipt["status"] == "provisioned"
    replacement = peer.variables["COCHEM_COLAB_ACCESS_SECRET"]
    assert replacement != label and peer.secret_values[replacement] == colab_token
    assert label not in peer.secret_values
    from cochem_base.interfaces.course_access import _project_writer
    writer_api = _project_writer(app_api, {"id": 22}, {"id": peer.project_id, "full_name": "student/project"})
    before = _access_stores(peer)
    peer.writes.clear()
    with pytest.raises(CourseAccessError, match="authoritative ControllerConfig"):
        sync_calculation_access(writer_api, "student/project", colab_dispatch_token=colab_token,
                                orca_token=config_colab.credentials["orca"],
                                cfour_token=config_colab.credentials["cfour"])
    assert _access_stores(peer) == before and peer.writes == []


def _access_stores(peer):
    return (dict(peer.variables), dict(peer.controller_variables),
            dict(peer.secret_values), dict(peer.codespaces_values))


def _sync_authority(peer, config):
    return {"author": "student",
        "controller_api": GitHubAPI(peer.controller_token, api_url=peer.url, allow_loopback=True),
        "app_api": GitHubAPI(app_jwt(config.app_id, config.private_key), api_url=peer.url, allow_loopback=True),
        "authority_api": GitHubAPI(api_url=peer.url, allow_loopback=True)}


@pytest.mark.parametrize("boundary", ["raw-writer", "missing-author", "missing-controller", "other-author", "other-repository-id"])
def test_sync_requires_authoritative_config_and_explicit_identity(peer, boundary):
    from cochem_base.interfaces.course_access import sync_calculation_access
    config = config_for(peer)
    kwargs = _sync_authority(peer, config)
    selected = config
    if boundary == "raw-writer":
        selected = kwargs["controller_api"]
    elif boundary == "missing-author":
        kwargs.pop("author")
    elif boundary == "missing-controller":
        kwargs.pop("controller_api")
    elif boundary == "other-author":
        kwargs["author"] = "another-student"
    else:
        kwargs["expected_repository_id"] = peer.project_id+1
    before = _access_stores(peer)
    with pytest.raises(CourseAccessError):
        sync_calculation_access(selected, EnrollmentRequest("student/project"), **kwargs)
    assert _access_stores(peer) == before and peer.writes == []


def test_sync_optional_colab_addition_preserves_exact_controller_fields(peer):
    from cochem_base.interfaces.course_access import sync_calculation_access
    config = config_for(peer, allowed_starter_shas=("b"*40,))
    credentials, targets = dict(config.credentials), dict(config.credential_targets)
    token = secrets.token_urlsafe(32)
    receipt = sync_calculation_access(config, EnrollmentRequest("student/project"),
        colab_dispatch_token=token, **_sync_authority(peer, config))
    assert receipt["status"] == "provisioned"
    assert receipt["approved_base_sha"] == config.approved_base_sha
    assert peer.secret_values[peer.variables["COCHEM_COLAB_ACCESS_SECRET"]] == token
    assert config.credentials == credentials and config.credential_targets == targets
    assert config.allowed_starter_shas == ("b"*40,)
    assert receipt["reader_metadata_verified"] == ["cfour", "orca", "source"]
    assert receipt["colab_access_verified"] is False


@pytest.mark.parametrize("boundary", ["conflicting-token", "raw-reader", "custom-label", "empty-token"])
def test_sync_conflicting_or_alternate_secret_inputs_refuse_before_writes(peer, boundary):
    from cochem_base.interfaces.course_access import sync_calculation_access
    config = config_for(peer)
    config = replace(config, credentials={**config.credentials, "colab": secrets.token_urlsafe(32)})
    kwargs = _sync_authority(peer, config)
    if boundary == "conflicting-token":
        kwargs["colab_dispatch_token"] = secrets.token_urlsafe(32)
    elif boundary == "raw-reader":
        kwargs["orca_token"] = config.credentials["orca"]
    elif boundary == "custom-label":
        kwargs["colab_secret_name"] = "UNOWNED_SECRET"
    else:
        kwargs["colab_dispatch_token"] = " "
    before = _access_stores(peer)
    with pytest.raises(CourseAccessError):
        sync_calculation_access(config, EnrollmentRequest("student/project"), **kwargs)
    assert _access_stores(peer) == before and peer.writes == []


def test_unowned_colab_actions_collision_is_preserved_before_writes(peer):
    config = config_for(peer)
    config = replace(config, credentials={**config.credentials, "colab": secrets.token_urlsafe(32)})
    peer.secret_values["COLAB_OFFLOAD_DISPATCH_TOKEN"] = secrets.token_urlsafe(32)
    before = _access_stores(peer)
    with pytest.raises(CourseAccessError, match="no authenticated controller ownership"):
        provision(peer, config)
    assert _access_stores(peer) == before and peer.writes == []


def test_absent_colab_keeps_unrelated_fixed_secrets_and_regular_enrollment(peer):
    peer.secret_values["COLAB_OFFLOAD_DISPATCH_TOKEN"] = secrets.token_urlsafe(32)
    peer.codespaces_values["COLAB_OFFLOAD_DISPATCH_TOKEN"] = secrets.token_urlsafe(32)
    original = (peer.secret_values["COLAB_OFFLOAD_DISPATCH_TOKEN"],
                peer.codespaces_values["COLAB_OFFLOAD_DISPATCH_TOKEN"])
    receipt = provision(peer, config_for(peer))
    assert receipt["status"] == "provisioned"
    assert receipt["available"] == ["cfour", "orca", "source"]
    assert (peer.secret_values["COLAB_OFFLOAD_DISPATCH_TOKEN"],
            peer.codespaces_values["COLAB_OFFLOAD_DISPATCH_TOKEN"]) == original
    owned = json.loads(ownership_record(peer))["payload"]
    assert "COLAB_OFFLOAD_DISPATCH_TOKEN" not in owned["actions"]
    assert "COLAB_OFFLOAD_DISPATCH_TOKEN" not in owned["codespaces"]
    assert "colab" not in owned["bindings"]


def _legacy_signed_colab_generation(peer):
    # A genuine signed controller record models the old fixed Actions generation.
    # No old unsafe production source is loaded or executed.
    from cochem_base.interfaces.course_access import _controller_ledger_api, _save_ownership
    config = config_for(peer)
    config = replace(config, credentials={**config.credentials, "colab": secrets.token_urlsafe(32)})
    provision(peer, config)
    label = peer.variables["COCHEM_COLAB_ACCESS_SECRET"]
    fixed = "COLAB_OFFLOAD_DISPATCH_TOKEN"
    peer.secret_values[fixed] = peer.secret_values.pop(label)
    peer.variables["COCHEM_COLAB_ACCESS_SECRET"] = fixed
    owned = json.loads(ownership_record(peer))["payload"]
    owned["actions"] = sorted((set(owned["actions"])-{label}) | {fixed})
    owned["bindings"]["colab"] = fixed
    app_api = _sync_authority(peer, config)["app_api"]
    _save_ownership(_controller_ledger_api(app_api, config), config, owned)
    return config


def test_signed_legacy_colab_rotation_preserves_old_values_until_switch(peer):
    config = _legacy_signed_colab_generation(peer)
    variables, _ledger, actions, codespaces = _access_stores(peer)
    replacement_token = secrets.token_urlsafe(32)
    replacement = replace(config, credentials={**config.credentials, "colab": replacement_token})
    peer.fail_variable_name = "COCHEM_COLAB_ACCESS_SECRET"
    with pytest.raises(CourseAccessError, match="incomplete"):
        provision(peer, replacement)
    assert peer.variables == variables
    assert all(peer.secret_values[name] == value for name, value in actions.items())
    assert peer.codespaces_values == codespaces
    assert json.loads(ownership_record(peer))["payload"]["state"] == "staging"
    peer.fail_variable_name = ""
    receipt = provision(peer, replacement)
    label = peer.variables["COCHEM_COLAB_ACCESS_SECRET"]
    assert receipt["status"] == "provisioned"
    assert label.startswith("COCHEM_ACCESS_") and label != "COLAB_OFFLOAD_DISPATCH_TOKEN"
    assert peer.secret_values[label] == replacement_token
    assert "COLAB_OFFLOAD_DISPATCH_TOKEN" not in peer.secret_values
    assert peer.codespaces_values["COLAB_OFFLOAD_DISPATCH_TOKEN"] == replacement_token
    assert not set(actions).intersection(peer.secret_values)


def test_signed_colab_without_replacement_config_holds_every_store(peer):
    config = _legacy_signed_colab_generation(peer)
    absent = replace(config, credentials={k: v for k, v in config.credentials.items() if k != "colab"})
    before = _access_stores(peer)
    peer.writes.clear()
    with pytest.raises(CourseAccessError, match="restore the reviewed configuration"):
        provision(peer, absent)
    assert _access_stores(peer) == before and peer.writes == []


def test_unreadable_colab_ownership_cannot_authorize_mutation(peer):
    config = _legacy_signed_colab_generation(peer)
    record = json.loads(ownership_record(peer))
    record["signature"] = base64.b64encode(b"not an authentic signature").decode()
    peer.controller_variables["COCHEM_ACCESS_PROJECT_42"] = json.dumps(record)
    before = _access_stores(peer)
    peer.writes.clear()
    with pytest.raises(CourseAccessError, match="ownership metadata could not be authenticated"):
        provision(peer, config)
    assert _access_stores(peer) == before and peer.writes == []


@pytest.mark.parametrize("with_target", [False, True])
def test_colab_secret_delivery_never_claims_provider_verification(peer, with_target):
    config = config_for(peer)
    targets = dict(config.credential_targets)
    if with_target:
        targets["colab"] = dict(targets["orca"])
    config = replace(config, credentials={**config.credentials, "colab": secrets.token_urlsafe(32)},
                     credential_targets=targets)
    receipt = provision(peer, config)
    assert receipt["reader_metadata_verified"] == ["cfour", "orca", "source"]
    assert receipt["colab_access_verified"] is False


def test_student_colab_monthly_quota_and_request_packaging(tmp_path):
    from cochem_base.interfaces.student_colab import (
        ColabQuotaExceededError,
        MonthlyStudentCuQuotaManager,
        package_student_colab_request,
        parse_student_colab_request,
        resolve_colab_dispatch_token,
        verify_student_colab_request_signature,
    )
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/course_project_access.yml").read_text()
    assert "COLAB_OFFLOAD_DISPATCH_TOKEN: ${{ secrets[vars.COCHEM_COLAB_ACCESS_SECRET] }}" in workflow

    ledger_file = tmp_path / "student_colab_cu_ledger.json"
    quota = MonthlyStudentCuQuotaManager(ledger_file, monthly_pool_cu=1750.0, allow_live_gh=False)
    current_month = quota.current_month_key()
    year, month = map(int, current_month.split("-"))
    next_month = f"{year + (month == 12):04d}-{month % 12 + 1:02d}"
    allowance_20 = quota.check_student_allowance("student-01", 10.0, month_key=current_month, n_students_override=20)
    assert allowance_20.per_student_cap_cu == 87.5
    assert allowance_20.allowed is True

    token = "cochem-colab-dispatch-" + secrets.token_urlsafe(24)
    env = {
        "COCHEM_COLAB_ACCESS_SECRET": "COLAB_OFFLOAD_DISPATCH_TOKEN",
        "COLAB_OFFLOAD_DISPATCH_TOKEN": token,
    }
    assert resolve_colab_dispatch_token(env) == token

    xyz = "4\nformaldehyde\nC 0.0 0.0 0.0\nO 0.0 0.0 1.203\nH 0.0 0.942 -0.587\nH 0.0 -0.942 -0.587\n"
    packaged = package_student_colab_request(
        student_id="student-01",
        job_id="orgo1-formaldehyde-freq",
        engine="ORCA",
        method="r2SCAN-3c",
        geometry_xyz=xyz,
        estimated_cu=12.5,
        quota_manager=quota,
        environ=env,
    )
    assert packaged["schema"] == "cochem.student-colab-request.v1"
    assert packaged["quota"]["used_cu"] == 12.5
    assert packaged["quota"]["remaining_cu"] == 75.0
    assert token not in json.dumps(packaged)
    assert verify_student_colab_request_signature(packaged, token) is True
    assert verify_student_colab_request_signature(packaged, "wrong-token") is False
    parsed = parse_student_colab_request("```json\n" + json.dumps(packaged) + "\n```")
    assert parsed["job_id"] == "orgo1-formaldehyde-freq"

    with pytest.raises(ColabQuotaExceededError, match="Monthly student CU cap exceeded"):
        quota.record_student_cu_usage("student-01", "orgo1-over-cap", 80.0, month_key=current_month, n_students_override=20)

    # Next calendar month auto-refreshes the student's quota to 0.0 used
    allowance_next = quota.check_student_allowance("student-01", 50.0, month_key=next_month, n_students_override=20)
    assert allowance_next.used_cu == 0.0
    assert allowance_next.allowed is True


