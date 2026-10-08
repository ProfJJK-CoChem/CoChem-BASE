"""Data-only enrollment and least-privilege private project provisioning.

This module belongs to the instructor's private controller. It never executes
student code and does not put the controller App key in student repositories.
Enrollment is GitHub UI data, not a student installation command.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib import error, parse, request

REQUEST_SCHEMA = "cochem.student-project-access.v1"
RECEIPT_SCHEMA = "cochem.student-project-access-receipt.v1"
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
_SHA = re.compile(r"[a-f0-9]{40}\Z")
_CRITICAL_PREFIXES = (
    "src/", "scripts/", ".scripts/", "ci_tools/", "ui/", "frontend/", "cochem/",
    "cochem_topos/", "cochem_geom/", "cochem_ml/", "cochem_mobile/", "cochem_torq/",
    "Libraries/", "setup/", ".github/", ".devcontainer/",
)
_CRITICAL_FILES = {
    "pyproject.toml", "MANIFEST.in", "Start_Here.ipynb", "cli.py", "pytest.ini",
    "pytest-srs.ini", ".core_infrastructure_hashring.json", ".pre-commit-config.yaml",
    ".gitattributes", "setup.py", "setup.cfg", "tox.ini", "uv.lock", "poetry.lock",
    "Pipfile", "Pipfile.lock",
}
BINDING_VARIABLES = {
    "orca": "COCHEM_ORCA_ACCESS_SECRET",
    "cfour": "COCHEM_CFOUR_ACCESS_SECRET",
    "source": "COCHEM_SOURCE_ACCESS_SECRET",
}


class CourseAccessError(RuntimeError):
    """The request was refused or access was not completely provisioned."""


class CourseAccessHTTPError(CourseAccessError):
    """Sanitized HTTP status, without an upstream body or credentials."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"GitHub refused the access operation (HTTP {status}).")


def repository_name(value: str) -> str:
    """Accept only a GitHub owner/name; reject URLs, path escapes and commands."""
    if not isinstance(value, str) or len(value.split("/")) != 2:
        raise CourseAccessError("Select a GitHub repository as owner/project.")
    if any(not _NAME.fullmatch(part) or part in {".", ".."} for part in value.split("/")):
        raise CourseAccessError("The project repository name is invalid.")
    return value


def _protected_source_path(name: str) -> bool:
    if name.startswith(_CRITICAL_PREFIXES) or name in _CRITICAL_FILES:
        return True
    if "/" in name:
        return False
    return (name.startswith("requirements") and name.endswith((".txt", ".lock", ".in"))
            or name.endswith((".py", ".sh", ".ps1", ".bat", ".cmd", ".command")))


@dataclass(frozen=True)
class EnrollmentRequest:
    repository: str
    engines: tuple[str, ...] = ("orca", "cfour")

    def __post_init__(self) -> None:
        repository_name(self.repository)
        if (not isinstance(self.engines, tuple) or any(not isinstance(value, str) for value in self.engines)
                or len(set(self.engines)) != len(self.engines)
                or any(engine not in {"orca", "cfour"} for engine in self.engines)):
            raise CourseAccessError("Select ORCA and/or CFOUR, or neither licensed engine.")

    def to_dict(self) -> dict[str, Any]:
        return {"schema": REQUEST_SCHEMA, "repository": self.repository,
                "engines": list(self.engines)}


def parse_enrollment(body: str) -> EnrollmentRequest:
    if not isinstance(body, str) or len(body.encode("utf-8")) > 2048:
        raise CourseAccessError("The enrollment request exceeds its data-only size limit.")
    body = body.strip()
    if body.startswith("```json\n") and body.endswith("\n```"):
        body = body[8:-4]
    def unique_object(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise CourseAccessError("Enrollment fields must be unique.")
            value[key] = item
        return value

    try:
        value = json.loads(body, object_pairs_hook=unique_object)
    except (ValueError, TypeError) as exc:
        raise CourseAccessError("Open the BASE-generated enrollment request without adding commands.") from exc
    if (not isinstance(value, dict) or set(value) != {"schema", "repository", "engines"}
            or value["schema"] != REQUEST_SCHEMA or not isinstance(value["engines"], list)):
        raise CourseAccessError("This is not a supported BASE enrollment request.")
    return EnrollmentRequest(value["repository"], tuple(value["engines"]))


def enrollment_links(controller_repository: str, app_slug: str, project_repository: str,
                     engines: tuple[str, ...] = ("orca", "cfour")) -> dict[str, str]:
    """Return browser links only; no credential or executable data enters URLs."""
    repository_name(controller_repository)
    if not isinstance(app_slug, str) or not _NAME.fullmatch(app_slug):
        raise CourseAccessError("The instructor's GitHub App link is not configured.")
    enrollment = EnrollmentRequest(project_repository, engines)
    body = "```json\n" + json.dumps(enrollment.to_dict(), separators=(",", ":")) + "\n```"
    query = parse.urlencode({"title": "CoChem private project access", "body": body})
    return {"install": f"https://github.com/apps/{app_slug}/installations/new",
            "enroll": f"https://github.com/{controller_repository}/issues/new?{query}"}


class _NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CourseAccessError("GitHub unexpectedly redirected; credentials were not forwarded.")


class GitHubAPI:
    """Bounded REST transport; errors never include tokens or response bodies."""

    def __init__(self, token: str = "", *, api_url: str = "https://api.github.com",
                 allow_loopback: bool = False) -> None:
        parsed = parse.urlsplit(api_url)
        production = api_url == "https://api.github.com"
        local_test = (allow_loopback and parsed.scheme == "http"
                      and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                      and not parsed.username and not parsed.password and not parsed.query
                      and not parsed.fragment and parsed.path == "")
        if not production and not local_test:
            raise CourseAccessError("Only GitHub's verified HTTPS API is supported.")
        self._token = token
        self._api_url = api_url
        self._opener = request.build_opener(_NoRedirect())

    def call(self, method: str, path: str, payload: dict | None = None) -> Any:
        if (method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}
                or not path.startswith("/") or path.startswith("//")
                or any(char in path for char in "\r\n#")):
            raise CourseAccessError("Invalid GitHub API operation.")
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "CoChem-course-access",
                   "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            headers["Authorization"] = "Bearer " + self._token
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = request.Request(self._api_url + path, data=data, headers=headers, method=method)
        try:
            with self._opener.open(req, timeout=30) as response:
                content = response.read(8 * 1024 * 1024 + 1)
        except error.HTTPError as exc:
            raise CourseAccessHTTPError(exc.code) from None
        except (error.URLError, TimeoutError, OSError):
            raise CourseAccessError("GitHub access could not be verified; retry after checking connectivity.") from None
        if len(content) > 8 * 1024 * 1024:
            raise CourseAccessError("GitHub metadata exceeds its bounded response limit.")
        try:
            return json.loads(content) if content else None
        except ValueError:
            raise CourseAccessError("GitHub returned invalid access metadata.") from None

    def with_token(self, token: str) -> GitHubAPI:
        return GitHubAPI(token, api_url=self._api_url,
                         allow_loopback=self._api_url.startswith("http://"))


def verify_calculation_project(api: GitHubAPI, repository: str) -> dict[str, Any]:
    """Recheck current visibility before releasing readers or licensed assets.

    Enrollment cannot establish future visibility: a project owner may change
    it later. Only the explicitly canonical maintainer repository is permitted
    to use this public route; student projects must remain independent/private.
    """
    repository_name(repository)
    metadata = api.call("GET", f"/repos/{repository}")
    owner = metadata.get("owner", {}) if isinstance(metadata, dict) else {}
    if (not isinstance(metadata, dict) or not isinstance(owner, dict)
            or str(metadata.get("full_name", "")).lower() != repository.lower()
            or str(owner.get("login", "")).lower() != repository.split("/")[0].lower()
            or metadata.get("archived") is not False or metadata.get("fork") is not False
            or type(metadata.get("private")) is not bool
            or type(metadata.get("id")) is not int or metadata["id"] <= 0):
        raise CourseAccessError("Current calculation repository identity, visibility or active state could not be verified.")
    canonical = repository.lower() == "ProfJJK-CoChem/CoChem-BASE".lower()
    if canonical:
        if owner.get("type") != "Organization":
            raise CourseAccessError("The canonical maintainer repository owner could not be verified.")
    elif metadata["private"] is not True or owner.get("type") != "User":
        raise CourseAccessError("Student calculations require an active private repository owned by the student's personal account.")
    return {"schema": "cochem.calculation-project-access.v1", "repository": metadata["full_name"],
            "repository_id": metadata["id"], "private": metadata["private"],
            "canonical_maintainer": canonical, "verified_at": datetime.now(timezone.utc).isoformat()}


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def app_jwt(app_id: str, private_key: str, *, now: int | None = None) -> str:
    """Sign a short-lived RS256 App assertion in memory, never in a shell/file."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa

    if not isinstance(app_id, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", app_id):
        raise CourseAccessError("Configure the instructor's numeric GitHub App ID.")
    timestamp = int(time.time()) if now is None else now
    try:
        key = serialization.load_pem_private_key(private_key.encode(), password=None)
    except (ValueError, TypeError):
        raise CourseAccessError("The instructor's App signing key is unavailable or invalid.") from None
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise CourseAccessError("GitHub App access requires an RSA key of at least 2048 bits.")
    header = _b64url(b'{"alg":"RS256","typ":"JWT"}')
    claims = _b64url(json.dumps({"iat": timestamp - 60, "exp": timestamp + 540,
                                "iss": app_id}, separators=(",", ":")).encode())
    message = (header + "." + claims).encode("ascii")
    signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
    return message.decode("ascii") + "." + _b64url(signature)


@dataclass(frozen=True)
class ControllerConfig:
    repository: str
    organization: str
    team_slug: str
    app_id: str
    approved_base_repository: str
    approved_base_sha: str
    app_slug: str = ""
    course_channel: str = ""
    allowed_starter_shas: tuple[str, ...] = ()
    private_key: str = field(default="", repr=False)
    credentials: dict[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        repository_name(self.repository)
        repository_name(self.approved_base_repository)
        if (self.repository.split("/")[0].lower() != self.organization.lower()
                or not _NAME.fullmatch(self.organization) or not _NAME.fullmatch(self.team_slug)
                or not _SHA.fullmatch(self.approved_base_sha)
                or not re.fullmatch(r"[1-9][0-9]{0,19}", self.app_id)
                or not _NAME.fullmatch(self.app_slug)
                or not isinstance(self.allowed_starter_shas, tuple)
                or len(self.allowed_starter_shas) > 8
                or any(not _SHA.fullmatch(value) for value in self.allowed_starter_shas)
                or set(self.credentials) - {"orca", "cfour", "source"}):
            raise CourseAccessError("The private instructor controller configuration is incomplete.")
        if self.course_channel and (not re.fullmatch(r"\.cochem/course-channels/[A-Za-z0-9_./-]{1,160}\.json", self.course_channel)
                                    or any(part in {"", ".", ".."} for part in self.course_channel.split("/"))):
            raise CourseAccessError("The instructor-approved course channel is invalid.")
        if any(not isinstance(value, str) or not value or "\x00" in value
               for value in self.credentials.values()):
            raise CourseAccessError("An instructor access credential is empty or invalid.")


def _installation(app_api: GitHubAPI, path: str, app_id: str) -> dict:
    value = app_api.call("GET", path)
    if (not isinstance(value, dict) or type(value.get("id")) is not int
            or value.get("app_id") != int(app_id)):
        raise CourseAccessError("The configured App is not installed for this repository or organization.")
    return value


def _installation_api(app_api: GitHubAPI, installation: dict, permissions: dict,
                      repository_id: int | None = None, repository: str | None = None) -> GitHubAPI:
    payload = {"permissions": permissions}
    if repository_id is not None:
        payload["repository_ids"] = [repository_id]
    elif repository is not None:
        payload["repositories"] = [repository_name(repository).split("/")[1]]
    value = app_api.call("POST", f"/app/installations/{installation['id']}/access_tokens", payload)
    if (not isinstance(value, dict) or not isinstance(value.get("token"), str)
            or not value["token"] or not isinstance(value.get("permissions"), dict)
            or any(value["permissions"].get(name) != access for name, access in permissions.items())
            or value["permissions"].get("metadata", "read") != "read"
            or any(name not in {*permissions, "metadata"} for name in value["permissions"])):
        raise CourseAccessError("The App could not issue the required least-privilege installation access.")
    try:
        expiry = datetime.fromisoformat(value["expires_at"].replace("Z", "+00:00"))
        remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
    except (KeyError, ValueError, TypeError):
        raise CourseAccessError("The App returned invalid installation-token expiry metadata.") from None
    if not 0 < remaining <= 3900:
        raise CourseAccessError("The App installation token is expired or exceeds the short-lived limit.")
    return app_api.with_token(value["token"])


def _tree(api: GitHubAPI, repository: str, revision: str) -> dict[str, tuple[str, str]]:
    value = api.call("GET", f"/repos/{repository}/git/trees/{parse.quote(revision, safe='')}?recursive=1")
    if (not isinstance(value, dict) or value.get("truncated") is not False
            or not isinstance(value.get("tree"), list)):
        raise CourseAccessError("The complete approved source tree could not be verified.")
    entries = {}
    for item in value["tree"]:
        if (not isinstance(item, dict) or not isinstance(item.get("path"), str)
                or item["path"] in entries or not _SHA.fullmatch(str(item.get("sha", "")))):
            raise CourseAccessError("GitHub returned an invalid or duplicate source-tree entry.")
        entries[item["path"]] = (item["sha"], str(item.get("mode", "")))
    return entries


def verify_project_source(project_api: GitHubAPI, authority_api: GitHubAPI,
                          config: ControllerConfig, project: dict) -> dict[str, str]:
    """Template history may differ; required executable blobs must be identical."""
    actual = _tree(project_api, project["full_name"], project["default_branch"])
    for revision in dict.fromkeys((config.approved_base_sha, *config.allowed_starter_shas)):
        approved = _tree(authority_api, config.approved_base_repository, revision)
        critical = {name: value for name, value in approved.items() if _protected_source_path(name)}
        if (critical and "scripts/run_student_research.py" in critical
                and ".github/workflows/student_research.yml" in critical
                and all(actual.get(name) == identity for name, identity in critical.items())
                and not any(_protected_source_path(name) and name not in approved for name in actual)):
            return {"starter_sha": revision, "source_digest": hashlib.sha256(
                json.dumps(critical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    raise CourseAccessError("The project starter is not an instructor-approved BASE revision. Ask the instructor to approve your compatible starter or use BASE's reviewed update; retain your student data.")


def encrypted_secret(public_key: str, value: str) -> str:
    """GitHub repository secret encryption with libsodium sealed boxes."""
    from nacl.public import PublicKey, SealedBox

    try:
        key = PublicKey(base64.b64decode(public_key, validate=True))
        encrypted = SealedBox(key).encrypt(value.encode("utf-8"))
    except (ValueError, TypeError):
        raise CourseAccessError("The project's GitHub secret-encryption public key is invalid.") from None
    return base64.b64encode(encrypted).decode("ascii")


def provision_project(config: ControllerConfig, enrollment: EnrollmentRequest, *,
                      author: str, controller_api: GitHubAPI,
                      app_api: GitHubAPI | None = None,
                      authority_api: GitHubAPI | None = None) -> dict[str, Any]:
    """Validate ownership, membership, installation and source before any write."""
    if not isinstance(author, str) or not _NAME.fullmatch(author):
        raise CourseAccessError("The enrollment author is invalid.")
    if enrollment.repository.split("/")[0].lower() != author.lower():
        raise CourseAccessError("Students may enroll only a private repository owned by their own GitHub account.")
    controller = controller_api.call("GET", f"/repos/{config.repository}")
    if (not isinstance(controller, dict) or controller.get("private") is not True
            or str(controller.get("full_name", "")).lower() != config.repository.lower()
            or controller.get("owner", {}).get("type") != "Organization"):
        raise CourseAccessError("Provisioning runs only in the instructor's configured private organization controller.")
    app_api = app_api or GitHubAPI(app_jwt(config.app_id, config.private_key))
    # The controller's read-only workflow token can read the public BASE tree
    # without spending the much smaller anonymous REST rate limit per student.
    authority_api = authority_api or controller_api
    organization_installation = _installation(app_api, f"/orgs/{config.organization}/installation", config.app_id)
    membership_api = _installation_api(app_api, organization_installation, {"members": "read"})
    membership = membership_api.call("GET", f"/orgs/{config.organization}/teams/{config.team_slug}/memberships/{author}")
    if not isinstance(membership, dict) or membership.get("state") != "active":
        raise CourseAccessError("Accept the lab organization/team invitation before requesting project access.")
    installation = _installation(app_api, f"/repos/{enrollment.repository}/installation", config.app_id)
    if (installation.get("repository_selection") != "selected"
            or installation.get("account", {}).get("type") != "User"
            or str(installation.get("account", {}).get("login", "")).lower() != author.lower()):
        raise CourseAccessError("Install the instructor App on your personal account and select only your private project.")
    # Repository metadata is accessible to the App JWT installation endpoint,
    # but obtain project metadata through a read-only selected installation token.
    read_api = _installation_api(app_api, installation, {"contents": "read"},
                                  repository=enrollment.repository)
    project = read_api.call("GET", f"/repos/{enrollment.repository}")
    if (not isinstance(project, dict) or project.get("private") is not True
            or project.get("archived") is not False or project.get("fork") is not False
            or project.get("owner", {}).get("type") != "User"
            or str(project.get("owner", {}).get("login", "")).lower() != author.lower()
            or str(project.get("full_name", "")).lower() != enrollment.repository.lower()
            or type(project.get("id")) is not int or project["id"] <= 0
            or not isinstance(project.get("default_branch"), str) or not project["default_branch"]):
        raise CourseAccessError("Select an active private personal project created with BASE's Use this template button.")
    source_binding = verify_project_source(read_api, authority_api, config, project)
    writer_api = _installation_api(app_api, installation,
        {"secrets": "write", "actions_variables": "write", "codespaces_secrets": "write"}, project["id"])
    selected = {kind: value for kind, value in config.credentials.items()
                if kind == "source" or kind in enrollment.engines}
    pubkey = writer_api.call("GET", f"/repos/{enrollment.repository}/actions/secrets/public-key")
    if (not isinstance(pubkey, dict) or not isinstance(pubkey.get("key_id"), str)
            or not pubkey["key_id"] or not isinstance(pubkey.get("key"), str)):
        raise CourseAccessError("GitHub has not provided the private project's Actions secret public key.")
    # All plaintext encryption is in memory. Fresh opaque labels avoid partially
    # overwriting a previously working credential during a failed rotation.
    binding = {}
    for kind, value in selected.items():
        label = "COCHEM_ACCESS_" + uuid.uuid4().hex.upper()
        writer_api.call("PUT", f"/repos/{enrollment.repository}/actions/secrets/{label}",
            {"encrypted_value": encrypted_secret(pubkey["key"], value), "key_id": pubkey["key_id"]})
        binding[BINDING_VARIABLES[kind]] = label
    codespaces_key = writer_api.call("GET", f"/repos/{enrollment.repository}/codespaces/secrets/public-key")
    if (not isinstance(codespaces_key, dict) or not isinstance(codespaces_key.get("key_id"), str)
            or not codespaces_key["key_id"] or not isinstance(codespaces_key.get("key"), str)):
        raise CourseAccessError("GitHub has not provided the project's Codespaces secret public key.")
    codespaces_values = {
        "COCHEM_ACCESS_CONTROLLER_REPOSITORY": config.repository,
        "COCHEM_ACCESS_APP_SLUG": config.app_slug,
        "COCHEM_SOURCE_CREDENTIAL": selected.get("source", ""),
    }
    for name, value in codespaces_values.items():
        writer_api.call("PUT", f"/repos/{enrollment.repository}/codespaces/secrets/{name}",
            {"encrypted_value": encrypted_secret(codespaces_key["key"], value),
             "key_id": codespaces_key["key_id"]})
    variables = {"COCHEM_APPROVED_BASE_SHA": config.approved_base_sha,
                 "COCHEM_COURSE_CHANNEL": config.course_channel,
                 **{name: binding.get(name, "") for name in BINDING_VARIABLES.values()}}
    for name, value in variables.items():
        # GET only bounded variable metadata; do not list unrelated secrets.
        try:
            writer_api.call("GET", f"/repos/{enrollment.repository}/actions/variables/{name}")
        except CourseAccessHTTPError as exc:
            if exc.status != 404:
                raise
            writer_api.call("POST", f"/repos/{enrollment.repository}/actions/variables",
                            {"name": name, "value": value})
        else:
            writer_api.call("PATCH", f"/repos/{enrollment.repository}/actions/variables/{name}",
                            {"name": name, "value": value})
    # Binding names and values are private repository metadata, never returned
    # as public acceptance evidence or posted into the enrollment issue.
    return {"schema": RECEIPT_SCHEMA, "repository": project["full_name"], "author": author,
            "approved_base_sha": config.approved_base_sha, **source_binding,
            "available": sorted(selected),
            "unavailable": sorted(set(enrollment.engines) - selected.keys()),
            "codespaces_source": "available" if "source" in selected else "unavailable",
            "engine_access_verified": False, "engine_execution_performed": False,
            "module_installation_performed": False,
            "status": "provisioned", "timestamp_utc": datetime.now(timezone.utc).isoformat()}
