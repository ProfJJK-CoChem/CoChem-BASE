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
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any
from urllib import error, parse, request

REQUEST_SCHEMA = "cochem.student-project-access.v1"
RECEIPT_SCHEMA = "cochem.student-project-access-receipt.v1"
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}\Z")
_SHA = re.compile(r"[a-f0-9]{40}\Z")
_DEVCONTAINER = ".devcontainer/devcontainer.json"
_PROJECT_RING = ".core_infrastructure_hashring.json"
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
    ".cochem/student-actions-admission.json",
}
BINDING_VARIABLES = {
    "orca": "COCHEM_ORCA_ACCESS_SECRET",
    "cfour": "COCHEM_CFOUR_ACCESS_SECRET",
    "source": "COCHEM_SOURCE_ACCESS_SECRET",
    "colab": "COCHEM_COLAB_ACCESS_SECRET",
}
_OWNERSHIP_PREFIX = "COCHEM_ACCESS_PROJECT_"
_OWNERSHIP_SCHEMA = "cochem.controller-owned-access.v2"
_OWNED_LABEL = re.compile(r"(?:COCHEM_ACCESS_[A-F0-9]{32}|COLAB_OFFLOAD_DISPATCH_TOKEN)\Z")
_PROJECT_VARIABLES = frozenset({"COCHEM_APPROVED_BASE_SHA", "COCHEM_COURSE_CHANNEL",
                                *BINDING_VARIABLES.values()})
_CODESPACES_NAMES = frozenset({"COCHEM_ACCESS_CONTROLLER_REPOSITORY",
                              "COCHEM_ACCESS_APP_SLUG", "COCHEM_SOURCE_CREDENTIAL",
                              "COLAB_OFFLOAD_DISPATCH_TOKEN"})


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
                 allow_loopback: bool = False, timeout_seconds: float = 30) -> None:
        parsed = parse.urlsplit(api_url)
        production = api_url == "https://api.github.com"
        local_test = (allow_loopback and parsed.scheme == "http"
                      and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                      and not parsed.username and not parsed.password and not parsed.query
                      and not parsed.fragment and parsed.path == "")
        if not production and not local_test:
            raise CourseAccessError("Only GitHub's verified HTTPS API is supported.")
        if type(timeout_seconds) not in {int, float} or not 0 < timeout_seconds <= 30:
            raise CourseAccessError("GitHub access requires a bounded positive transport timeout.")
        self._token = token
        self._api_url = api_url
        self._timeout_seconds = timeout_seconds
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
            with self._opener.open(req, timeout=self._timeout_seconds) as response:
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
                         allow_loopback=self._api_url.startswith("http://"),
                         timeout_seconds=self._timeout_seconds)


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
    credential_targets: dict[str, dict[str, str]] = field(default_factory=dict)

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
                or set(self.credentials) - {"orca", "cfour", "source", "colab"}
                or not isinstance(self.credential_targets, dict)
                or set(self.credential_targets) - {"orca", "cfour", "source", "colab"}):
            raise CourseAccessError("The private instructor controller configuration is incomplete.")
        if self.course_channel and (not re.fullmatch(r"\.cochem/course-channels/[A-Za-z0-9_./-]{1,160}\.json", self.course_channel)
                                    or any(part in {"", ".", ".."} for part in self.course_channel.split("/"))):
            raise CourseAccessError("The instructor-approved course channel is invalid.")
        if any(not isinstance(value, str) or not value or "\x00" in value
               for value in self.credentials.values()):
            raise CourseAccessError("An instructor access credential is empty or invalid.")
        for kind, target in self.credential_targets.items():
            expected = {"repository", "revision"} if kind == "source" else {
                "repository", "release_tag", "archive_name", "sha256"}
            if (not isinstance(target, dict) or set(target) != expected
                    or any(not isinstance(value, str) or not value or len(value) > 255
                           for value in target.values())):
                raise CourseAccessError("Configure reviewed immutable credential-readability targets.")
            repository_name(target["repository"])
            if ((kind == "source" and not _SHA.fullmatch(target["revision"]))
                    or (kind != "source" and (not re.fullmatch(r"[a-f0-9]{64}", target["sha256"])
                        or not _NAME.fullmatch(target["release_tag"])
                        or not _NAME.fullmatch(target["archive_name"])) )):
                raise CourseAccessError("The reviewed credential-readability target is invalid.")


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


def _git_blob_sha(content: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()


def _approved_configuration(api: GitHubAPI, config: ControllerConfig,
                            template_sha: str) -> tuple[bytes, dict]:
    """Read bounded authenticated JSON; no project data supplies authority."""
    value = api.call("GET", f"/repos/{config.approved_base_repository}/git/blobs/{template_sha}")
    if (not isinstance(value, dict) or value.get("sha") != template_sha
            or value.get("encoding") != "base64" or type(value.get("size")) is not int
            or not 0 < value["size"] <= 65536 or not isinstance(value.get("content"), str)
            or len(value["content"]) > 90000):
        raise CourseAccessError("The approved Codespaces configuration could not be read.")
    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError("duplicate configuration key")
            result[key] = item
        return result

    try:
        content = base64.b64decode("".join(value["content"].split()), validate=True)
        if len(content) != value["size"] or _git_blob_sha(content) != template_sha:
            raise ValueError("configuration blob identity differs")
        document = json.loads(content, object_pairs_hook=unique_object)
        if not isinstance(document, dict):
            raise ValueError("configuration must be an object")
        return content, document
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise CourseAccessError("The approved Codespaces configuration is invalid; ask the instructor to update BASE.") from None


def _codespaces_content(document: dict, project: str) -> bytes:
    """Replace cross-owner requests, retaining every approved launch setting."""
    repository_name(project)
    try:
        codespaces = document["customizations"]["codespaces"]
        if not isinstance(codespaces["repositories"], dict):
            raise ValueError("repository permissions must be explicit")
        codespaces["repositories"] = {project: {"permissions": {"actions": "write", "contents": "write"}}}
        return (json.dumps(document, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise CourseAccessError("The approved Codespaces configuration is invalid; ask the instructor to update BASE.") from None


def _project_codespaces_configuration(api: GitHubAPI, config: ControllerConfig,
                                      template_sha: str, project: str) -> bytes:
    return _codespaces_content(_approved_configuration(api, config, template_sha)[1], project)


def _project_codespaces_pair(api: GitHubAPI, config: ControllerConfig,
                             template_sha: str, ring_sha: str, project: str) -> dict[str, bytes]:
    """Derive the sole project grant and exactly its one changed ring digest."""
    original, document = _approved_configuration(api, config, template_sha)
    _, ring = _approved_configuration(api, config, ring_sha)
    files = ring.get("files")
    if (set(ring) != {"schema_version", "algorithm", "files"}
            or type(ring.get("schema_version")) is not int or ring["schema_version"] != 1
            or ring.get("algorithm") != "sha256" or not isinstance(files, dict)
            or not files or _PROJECT_RING in files
            or any(not isinstance(name, str) or not name or name.startswith("/")
                   or "\\" in name or any(part in {"", ".", ".."} for part in name.split("/"))
                   or not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest)
                   for name, digest in files.items())
            or files.get(_DEVCONTAINER) != hashlib.sha256(original).hexdigest()):
        raise CourseAccessError("The approved infrastructure ring does not bind the approved Codespaces template.")
    content = _codespaces_content(document, project)
    files[_DEVCONTAINER] = hashlib.sha256(content).hexdigest()
    return {_DEVCONTAINER: content,
            _PROJECT_RING: (json.dumps(ring, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")}


def _project_revision(api: GitHubAPI, project: dict) -> str:
    branch = parse.quote(project["default_branch"], safe="")
    value = api.call("GET", f"/repos/{project['full_name']}/git/ref/heads/{branch}")
    item = value.get("object") if isinstance(value, dict) else None
    if (not isinstance(item, dict) or item.get("type") != "commit"
            or not _SHA.fullmatch(str(item.get("sha", "")))):
        raise CourseAccessError("The project's current source revision could not be verified.")
    return item["sha"]


def verify_project_source(project_api: GitHubAPI, authority_api: GitHubAPI,
                          config: ControllerConfig, project: dict, *,
                          allow_migration: bool = False) -> dict[str, str]:
    """Require the exact paired grant; legacy source is migration input only."""
    project_revision = _project_revision(project_api, project)
    actual = _tree(project_api, project["full_name"], project_revision)
    for revision in dict.fromkeys((config.approved_base_sha, *config.allowed_starter_shas)):
        approved = _tree(authority_api, config.approved_base_repository, revision)
        critical = {name: value for name, value in approved.items() if _protected_source_path(name)}
        template = critical.get(_DEVCONTAINER)
        ring = critical.get(_PROJECT_RING)
        if not template or template[1] != "100644" or not ring or ring[1] != "100644":
            continue
        generated = _project_codespaces_pair(authority_api, config, template[0], ring[0], project["full_name"])
        derived = {name: (_git_blob_sha(content), "100644") for name, content in generated.items()}
        pair = (actual.get(_DEVCONTAINER), actual.get(_PROJECT_RING))
        state = ("paired" if pair == (derived[_DEVCONTAINER], derived[_PROJECT_RING]) else
                 "canonical_migration" if pair == (template, ring) else
                 "legacy_migration" if pair == (derived[_DEVCONTAINER], ring) else "invalid")
        if (critical and "scripts/run_student_research.py" in critical
                and ".github/workflows/student_research.yml" in critical
                and (state == "paired" or allow_migration and state in {"canonical_migration", "legacy_migration"})
                and all(name in derived or actual.get(name) == identity
                        for name, identity in critical.items())
                and not any(_protected_source_path(name) and name not in approved for name in actual)):
            return {"starter_sha": revision, "project_revision": project_revision,
                    "source_state": state,
                    "devcontainer_template_sha": template[0],
                    "ring_template_sha": ring[0],
                    "devcontainer_current_sha": actual[_DEVCONTAINER][0],
                    "ring_current_sha": actual[_PROJECT_RING][0],
                    "source_digest": hashlib.sha256(
                        json.dumps(critical, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                    "project_source_digest": hashlib.sha256(
                        json.dumps({name: actual[name] for name in critical}, sort_keys=True,
                                   separators=(",", ":")).encode()).hexdigest()}
    raise CourseAccessError("The project starter is not an instructor-approved BASE revision. Ask the instructor to approve your compatible starter or use BASE's reviewed update; retain your student data.")


def _configure_project_codespaces(app_api: GitHubAPI, installation: dict,
                                  project_api: GitHubAPI, authority_api: GitHubAPI,
                                  config: ControllerConfig, project: dict,
                                  binding: dict[str, str]) -> dict[str, Any]:
    contents = _project_codespaces_pair(authority_api, config,
        binding["devcontainer_template_sha"], binding["ring_template_sha"], project["full_name"])
    digests = {name: _git_blob_sha(content) for name, content in contents.items()}
    result = {"codespaces_configuration_sha": digests[_DEVCONTAINER],
              "codespaces_ring_sha": digests[_PROJECT_RING],
              "codespaces_binding_schema": "cochem.codespaces-project-binding/2",
              "codespaces_authorization_required": True, "project_revision": binding["project_revision"]}
    if (binding["devcontainer_current_sha"] == digests[_DEVCONTAINER]
            and binding["ring_current_sha"] == digests[_PROJECT_RING]):
        return result
    try:
        writer = _installation_api(app_api, installation, {"contents": "write"}, project["id"])
    except CourseAccessHTTPError as exc:
        if exc.status not in {403, 422}:
            raise
        raise CourseAccessError("The instructor must change the lab GitHub App's Contents permission to Read and write, approve that change for this project, then retry setup. BASE uses it only to configure this project's Codespace.") from None
    prefix = f"/repos/{project['full_name']}/git"
    commit = project_api.call("GET", prefix + "/commits/" + binding["project_revision"])
    if (not isinstance(commit, dict) or commit.get("sha") != binding["project_revision"]
            or not isinstance(commit.get("tree"), dict)
            or not _SHA.fullmatch(str(commit["tree"].get("sha", "")))):
        raise CourseAccessError("The verified project tree could not be read; retry setup.")
    entries = []
    for name, content in contents.items():
        blob = writer.call("POST", prefix + "/blobs", {
            "encoding": "base64", "content": base64.b64encode(content).decode("ascii")})
        if not isinstance(blob, dict) or blob.get("sha") != digests[name]:
            raise CourseAccessError("GitHub did not retain the exact project Codespaces configuration pair.")
        entries.append({"path": name, "mode": "100644", "type": "blob", "sha": digests[name]})
    tree = writer.call("POST", prefix + "/trees", {"base_tree": commit["tree"]["sha"],
        "tree": entries})
    if not isinstance(tree, dict) or not _SHA.fullmatch(str(tree.get("sha", ""))):
        raise CourseAccessError("GitHub did not prepare the project Codespaces configuration.")
    saved = writer.call("POST", prefix + "/commits", {
        "message": "Bind this project's Codespace and reviewed infrastructure ring",
        "tree": tree["sha"], "parents": [binding["project_revision"]]})
    if not isinstance(saved, dict) or not _SHA.fullmatch(str(saved.get("sha", ""))):
        raise CourseAccessError("GitHub did not save the project Codespaces configuration.")
    try:
        updated = writer.call("PATCH", prefix + "/refs/heads/" + parse.quote(project["default_branch"], safe=""),
                              {"sha": saved["sha"], "force": False})
    except CourseAccessHTTPError as exc:
        if exc.status not in {403, 409, 422}:
            raise
        raise CourseAccessError("The project's setup update was refused. Its branch may have changed or may restrict App changes. Ask the instructor to check the App's access and retry; existing project files were not overwritten.") from None
    if (not isinstance(updated, dict) or not isinstance(updated.get("object"), dict)
            or updated["object"].get("type") != "commit" or updated["object"].get("sha") != saved["sha"]):
        raise CourseAccessError("The project's Codespaces setup update could not be confirmed.")
    result["project_revision"] = saved["sha"]
    return result


def encrypted_secret(public_key: str, value: str) -> str:
    """GitHub repository secret encryption with libsodium sealed boxes."""
    from nacl.public import PublicKey, SealedBox

    try:
        key = PublicKey(base64.b64decode(public_key, validate=True))
        encrypted = SealedBox(key).encrypt(value.encode("utf-8"))
    except (ValueError, TypeError):
        raise CourseAccessError("The project's GitHub secret-encryption public key is invalid.") from None
    return base64.b64encode(encrypted).decode("ascii")


def _variable(api: GitHubAPI, repository: str, name: str) -> str | None:
    try:
        value = api.call("GET", f"/repos/{repository}/actions/variables/{name}")
    except CourseAccessHTTPError as exc:
        if exc.status == 404:
            return None
        raise
    if (not isinstance(value, dict) or value.get("name") != name
            or not isinstance(value.get("value"), str) or len(value["value"]) > 32768):
        raise CourseAccessError("GitHub returned invalid controller variable metadata.")
    return value["value"]


def _write_variable(api: GitHubAPI, repository: str, name: str, value: str) -> None:
    exists = _variable(api, repository, name) is not None
    api.call("PATCH" if exists else "POST",
             f"/repos/{repository}/actions/variables" + ("/" + name if exists else ""),
             {"name": name, "value": value})
    if _variable(api, repository, name) != value:
        raise CourseAccessError("The project's controller variable update could not be confirmed.")


def _secret_exists(api: GitHubAPI, repository: str, store: str, name: str) -> bool:
    try:
        value = api.call("GET", f"/repos/{repository}/{store}/secrets/{name}")
    except CourseAccessHTTPError as exc:
        if exc.status == 404:
            return False
        raise
    if not isinstance(value, dict) or value.get("name") != name:
        raise CourseAccessError("GitHub returned invalid controller secret metadata.")
    return True


def _ownership_key(config: ControllerConfig):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    try:
        key = serialization.load_pem_private_key(config.private_key.encode(), password=None)
    except (ValueError, TypeError):
        raise CourseAccessError("The controller ownership signing key is unavailable.") from None
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise CourseAccessError("Controller ownership requires an RSA key of at least 2048 bits.")
    return key


def _ownership(api: GitHubAPI, config: ControllerConfig, project: dict) -> dict:
    """Read the latest ownership record only from the private controller.

    A student can replay or delete any project variable, including a historical
    signed ownership envelope. None is read here. The private controller store
    supplies freshness; the signature authenticates its bounded deletion scope.
    This still does not authorize a new download/calculation. Callers must use
    the controller workflow's common serialization group for every mutation.
    """
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    identity = {"schema": _OWNERSHIP_SCHEMA, "controller": config.repository,
                "app_id": config.app_id, "repository": project["full_name"],
                "repository_id": project["id"]}
    value = _variable(api, config.repository, _OWNERSHIP_PREFIX + str(project["id"]))
    if value is None:
        return {**identity, "actions": [], "codespaces": [], "variables": [],
                "bindings": {}, "state": "new"}
    try:
        def unique(pairs):
            result = {}
            for name, item in pairs:
                if name in result:
                    raise ValueError("duplicate ownership field")
                result[name] = item
            return result
        envelope = json.loads(value, object_pairs_hook=unique)
        if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}:
            raise ValueError("invalid ownership envelope")
        owned = envelope["payload"]
        signature = base64.b64decode(envelope["signature"], validate=True)
        _ownership_key(config).public_key().verify(signature,
            json.dumps(owned, sort_keys=True, separators=(",", ":")).encode(),
            padding.PKCS1v15(), hashes.SHA256())
        if (not isinstance(owned, dict) or set(owned) != {*identity, "actions", "codespaces", "variables", "bindings", "state"}
                or any(owned.get(name) != item for name, item in identity.items())
                or owned["state"] not in {"staging", "active", "revoking", "revoked"}):
            raise ValueError("invalid ownership identity")
        for store, allowed in (("actions", None), ("codespaces", _CODESPACES_NAMES),
                               ("variables", _PROJECT_VARIABLES)):
            names = owned[store]
            if (not isinstance(names, list) or len(names) > 128
                    or any(not isinstance(name, str) for name in names)
                    or len(set(names)) != len(names)
                    or any(not _OWNED_LABEL.fullmatch(name) if allowed is None else name not in allowed
                           for name in names)):
                raise ValueError("invalid owned namespace")
        bindings = owned["bindings"]
        if (not isinstance(bindings, dict) or set(bindings) - BINDING_VARIABLES.keys()
                or any(not isinstance(label, str) or label not in owned["actions"]
                       for label in bindings.values())):
            raise ValueError("invalid owned bindings")
        return owned
    except (InvalidSignature, ValueError, TypeError, KeyError, UnicodeError):
        raise CourseAccessError("Controller ownership metadata could not be authenticated; no existing credentials were removed. Ask the instructor to reconcile this project's controller signing key and ownership record.") from None


def _save_ownership(api: GitHubAPI, config: ControllerConfig, owned: dict) -> None:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    body = json.dumps(owned, sort_keys=True, separators=(",", ":")).encode()
    signature = _ownership_key(config).sign(body, padding.PKCS1v15(), hashes.SHA256())
    value = json.dumps({"payload": owned, "signature": base64.b64encode(signature).decode()},
                       sort_keys=True, separators=(",", ":"))
    if len(value) > 32768:
        raise CourseAccessError("Controller ownership metadata exceeds its bound; reconcile pending cleanup first.")
    _write_variable(api, config.repository, _OWNERSHIP_PREFIX + str(owned["repository_id"]), value)


def _cleanup_owned(api: GitHubAPI, ledger_api: GitHubAPI, config: ControllerConfig, owned: dict, *,
                   actions: set[str], codespaces: set[str], state: str) -> dict:
    """Delete only signed owned labels; retain failures for an explicit retry."""
    pending = 0
    for store, retained in (("actions", actions), ("codespaces", codespaces)):
        for name in tuple(owned[store]):
            if name in retained:
                continue
            try:
                try:
                    api.call("DELETE", f"/repos/{owned['repository']}/{store}/secrets/{name}")
                except CourseAccessHTTPError as exc:
                    if exc.status != 404:
                        raise
                if _secret_exists(api, owned["repository"], store, name):
                    raise CourseAccessError("A removed controller credential still exists.")
            except CourseAccessError:
                pending += 1
            else:
                owned[store].remove(name)
    owned["state"] = state
    _save_ownership(ledger_api, config, owned)
    return {"cleanup_pending": pending, "credential_values_revoked": False,
            "existing_codespaces_refresh_required": True, "current_job_authorization_enforced": False}


def _project_context(config: ControllerConfig, enrollment: EnrollmentRequest, *,
                     author: str, controller_api: GitHubAPI,
                     app_api: GitHubAPI | None = None,
                     require_membership: bool = True,
                     require_active_project: bool = True) -> tuple[GitHubAPI, dict, GitHubAPI, dict]:
    """Recheck authority; withdrawal does not require continued course membership."""
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
    if require_membership and not _active_member(app_api, config, author):
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
    if (not isinstance(project, dict)
            or (require_active_project and (project.get("private") is not True
                or project.get("archived") is not False or project.get("fork") is not False))
            or project.get("owner", {}).get("type") != "User"
            or str(project.get("owner", {}).get("login", "")).lower() != author.lower()
            or str(project.get("full_name", "")).lower() != enrollment.repository.lower()
            or type(project.get("id")) is not int or project["id"] <= 0
            or not isinstance(project.get("default_branch"), str) or not project["default_branch"]):
        raise CourseAccessError("Select an active private personal project created with BASE's Use this template button.")
    return app_api, installation, read_api, project


def _active_member(app_api: GitHubAPI, config: ControllerConfig, author: str) -> bool:
    installation = _installation(app_api, f"/orgs/{config.organization}/installation", config.app_id)
    api = _installation_api(app_api, installation, {"members": "read"})
    try:
        value = api.call("GET", f"/orgs/{config.organization}/teams/{config.team_slug}/memberships/{author}")
    except CourseAccessHTTPError as exc:
        if exc.status == 404:
            return False
        raise
    if not isinstance(value, dict) or value.get("state") not in {"active", "pending"}:
        raise CourseAccessError("The current course-team membership could not be verified.")
    return value["state"] == "active"


def _project_writer(app_api: GitHubAPI, installation: dict, project: dict) -> GitHubAPI:
    return _installation_api(app_api, installation,
        {"secrets": "write", "actions_variables": "write", "codespaces_secrets": "write"}, project["id"])


def _controller_ledger_api(app_api: GitHubAPI, config: ControllerConfig) -> GitHubAPI:
    """Scope the trusted ownership store token to the private controller alone."""
    installation = _installation(app_api, f"/orgs/{config.organization}/installation", config.app_id)
    return _installation_api(app_api, installation, {"actions_variables": "write"},
                             repository=config.repository)


class ControllerInboxStore:
    """Signed request receipts in the controller, never in a student project.

    Like ownership records, these require the one controller-wide lifecycle
    writer. Receipts prove processing, not continuing authorization. Store only
    bounded nonsecret data; the App key and readers never enter this ledger.
    """

    def __init__(self, config: ControllerConfig, *, app_api: GitHubAPI | None = None):
        self.config = config
        app_api = app_api or GitHubAPI(app_jwt(config.app_id, config.private_key))
        self.app_api = app_api
        self.api = _controller_ledger_api(app_api, config)

    def _identity(self, key: str) -> dict:
        if not re.fullmatch(r"COCHEM_ACCESS_INBOX_(?:ISSUE_[1-9][0-9]{0,19}|HOLD_[1-9][0-9]{0,19}|CURSOR)", key):
            raise CourseAccessError("Invalid controller inbox record identity.")
        return {"schema": "cochem.controller-inbox.v1", "controller": self.config.repository,
                "app_id": self.config.app_id, "key": key}

    def read(self, key: str) -> dict | None:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        identity = self._identity(key)
        value = _variable(self.api, self.config.repository, key)
        if value is None:
            return None
        def unique_object(pairs):
            result = {}
            for name, item in pairs:
                if name in result:
                    raise ValueError("duplicate inbox field")
                result[name] = item
            return result
        try:
            envelope = json.loads(value, object_pairs_hook=unique_object)
            if not isinstance(envelope, dict) or set(envelope) != {"payload", "signature"}:
                raise ValueError("invalid inbox envelope")
            payload = envelope["payload"]
            if (not isinstance(payload, dict) or set(payload) != {*identity, "data"}
                    or any(payload[name] != expected for name, expected in identity.items())
                    or not isinstance(payload["data"], dict)):
                raise ValueError("record identity differs")
            body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            _ownership_key(self.config).public_key().verify(
                base64.b64decode(envelope["signature"], validate=True), body,
                padding.PKCS1v15(), hashes.SHA256())
            return payload["data"]
        except (InvalidSignature, ValueError, TypeError, KeyError):
            raise CourseAccessError("Controller inbox metadata could not be authenticated; no request was replayed.") from None

    def write(self, key: str, data: dict) -> None:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        payload = {**self._identity(key), "data": data}
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signature = _ownership_key(self.config).sign(body, padding.PKCS1v15(), hashes.SHA256())
        value = json.dumps({"payload": payload, "signature": base64.b64encode(signature).decode()},
                           sort_keys=True, separators=(",", ":"))
        if len(value) > 16384:
            raise CourseAccessError("Controller inbox record exceeds its data-only bound.")
        _write_variable(self.api, self.config.repository, key, value)

    def hold_key(self, repository: str) -> str:
        """Resolve immutable identity through selected App read access.

        A repository rename must not evade an instructor's withdrawal. The name
        routes this read; only the verified immutable ID names the hold record.
        Withdrawal also supports archived/public projects, as the lifecycle does.
        """
        repository_name(repository)
        installation = _installation(self.app_api, f"/repos/{repository}/installation", self.config.app_id)
        reader = _installation_api(self.app_api, installation, {"contents": "read"}, repository=repository)
        project = reader.call("GET", f"/repos/{repository}")
        owner = project.get("owner", {}) if isinstance(project, dict) else {}
        if (not isinstance(project, dict) or not isinstance(owner, dict)
                or type(project.get("id")) is not int or not 0 < project["id"] < 10**20
                or str(project.get("full_name", "")).lower() != repository.lower()
                or owner.get("type") != "User"
                or str(owner.get("login", "")).lower() != repository.split("/")[0].lower()):
            raise CourseAccessError("The inbox project immutable identity could not be verified.")
        return "COCHEM_ACCESS_INBOX_HOLD_" + str(project["id"])

    def held_project(self, repository: str) -> tuple[int, bool]:
        """Return the same verified immutable ID used for the hold decision."""
        key = self.hold_key(repository)
        repository_id = int(key.rsplit("_", 1)[1])
        value = self.read(key)
        if value is None:
            return repository_id, False
        if (set(value) != {"repository_id", "held"} or type(value["held"]) is not bool
                or type(value["repository_id"]) is not int
                or value["repository_id"] != repository_id):
            raise CourseAccessError("Controller inbox project hold is invalid.")
        return repository_id, value["held"]

    def held(self, repository: str) -> bool:
        return self.held_project(repository)[1]

    def hold_repository_id(self, repository_id: int, held: bool) -> None:
        """Write a hold for an already verified target, without resolving a name."""
        if type(repository_id) is not int or not 0 < repository_id < 10**20 or type(held) is not bool:
            raise CourseAccessError("The controller inbox hold identity is invalid.")
        key = "COCHEM_ACCESS_INBOX_HOLD_" + str(repository_id)
        self.write(key, {"repository_id": repository_id, "held": held})

    def hold(self, repository: str, held: bool) -> None:
        key = self.hold_key(repository)
        self.hold_repository_id(int(key.rsplit("_", 1)[1]), held)


def _public_key(api: GitHubAPI, repository: str, store: str) -> dict:
    value = api.call("GET", f"/repos/{repository}/{store}/secrets/public-key")
    if (not isinstance(value, dict) or not isinstance(value.get("key_id"), str)
            or not value["key_id"] or not isinstance(value.get("key"), str)):
        raise CourseAccessError("GitHub has not provided the project's secret-encryption public key.")
    return value


def _put_secret(api: GitHubAPI, repository: str, store: str, name: str,
                value: str, public_key: dict) -> None:
    api.call("PUT", f"/repos/{repository}/{store}/secrets/{name}",
             {"encrypted_value": encrypted_secret(public_key["key"], value), "key_id": public_key["key_id"]})
    if not _secret_exists(api, repository, store, name):
        raise CourseAccessError("GitHub did not retain the project's controller credential metadata.")


def _verify_reader_metadata(api: GitHubAPI, config: ControllerConfig,
                            selected: dict[str, str]) -> list[str]:
    """Probe the new readers against trusted pinned targets before replacing any.

    GitHub release digests are authenticated metadata, not an independent hash
    of downloaded bytes. This cannot certify binary integrity or execution.
    Targets come only from reviewed controller source/configuration, never from
    the student project, an enrollment issue or its writable ownership record.
    """
    verified = []
    for kind, token in selected.items():
        if kind == "colab":
            if not isinstance(token, str) or not token.strip():
                raise CourseAccessError("The Google Colab offload dispatch token is empty or invalid.")
            # Secret delivery is not authenticated Colab/provider access.
            continue
        target = config.credential_targets.get(kind)
        if target is None:
            raise CourseAccessError("A replacement reader has no reviewed immutable readability target; existing credentials and bindings were preserved.")
        reader = api.with_token(token)
        repository = target["repository"]
        metadata = reader.call("GET", f"/repos/{repository}")
        if (not isinstance(metadata, dict)
                or str(metadata.get("full_name", "")).lower() != repository.lower()
                or (kind != "source" and metadata.get("private") is not True)):
            raise CourseAccessError("A replacement reader could not verify its reviewed repository; existing credentials and bindings were preserved.")
        if kind == "source":
            commit = reader.call("GET", f"/repos/{repository}/git/commits/{target['revision']}")
            if (not isinstance(commit, dict) or commit.get("sha") != target["revision"]
                    or not _tree(reader, repository, target["revision"])):
                raise CourseAccessError("A replacement source reader could not read the exact reviewed revision; existing credentials and bindings were preserved.")
        else:
            release = reader.call("GET", f"/repos/{repository}/releases/tags/" + parse.quote(target["release_tag"], safe=""))
            if (not isinstance(release, dict) or release.get("tag_name") != target["release_tag"]
                    or release.get("draft") is not False or not isinstance(release.get("assets"), list)
                    or len(release["assets"]) > 128):
                raise CourseAccessError("A replacement engine reader could not verify the reviewed release metadata; existing credentials and bindings were preserved.")
            assets = [item for item in release["assets"] if isinstance(item, dict)
                      and item.get("name") == target["archive_name"]]
            if (len(assets) != 1 or type(assets[0].get("id")) is not int or assets[0]["id"] <= 0
                    or type(assets[0].get("size")) is not int or assets[0]["size"] <= 0
                    or assets[0].get("state") != "uploaded"
                    or assets[0].get("digest") != "sha256:" + target["sha256"]):
                raise CourseAccessError("A replacement engine reader could not verify the pinned asset name and digest metadata; existing credentials and bindings were preserved.")
        verified.append(kind)
    return sorted(verified)


def provision_project(config: ControllerConfig, enrollment: EnrollmentRequest, *,
                      author: str, controller_api: GitHubAPI,
                      app_api: GitHubAPI | None = None,
                      authority_api: GitHubAPI | None = None,
                      expected_repository_id: int | None = None) -> dict[str, Any]:
    """Stage replacements, confirm bindings, then retire signed owned labels.

    GitHub cannot return encrypted secret values. Readback confirms metadata,
    not credential validity or licensed-engine access. Copied shared readers
    cannot provide issuer-side revocation or current-job membership enforcement.
    """
    app_api, installation, read_api, project = _project_context(config, enrollment,
        author=author, controller_api=controller_api, app_api=app_api)
    if expected_repository_id is not None and (type(expected_repository_id) is not int
            or expected_repository_id <= 0 or project["id"] != expected_repository_id):
        raise CourseAccessError("The project immutable identity changed after the inbox hold check; no project access was written.")
    authority_api = authority_api or controller_api
    source_binding = verify_project_source(read_api, authority_api, config, project, allow_migration=True)
    writer_api = _project_writer(app_api, installation, project)
    ledger_api = _controller_ledger_api(app_api, config)
    owned = _ownership(ledger_api, config, project)
    if "colab" in owned["bindings"] and "colab" not in config.credentials:
        raise CourseAccessError("Existing signed Colab access has no configured replacement; all access was preserved. The instructor must restore the reviewed configuration or use an explicit reviewed withdrawal route.")
    previous = {name: _variable(writer_api, enrollment.repository, name) for name in _PROJECT_VARIABLES}
    # Never adopt an unsigned legacy selector or an unrelated existing fixed
    # Codespaces secret as deletion authority. Explicit migration is separate.
    if any(value is not None and name not in owned["variables"] for name, value in previous.items()):
        raise CourseAccessError("Existing project access settings have no authenticated controller ownership record; instructor reconciliation is required before replacement.")
    for name in _CODESPACES_NAMES - set(owned["codespaces"]):
        if name == "COLAB_OFFLOAD_DISPATCH_TOKEN" and "colab" not in config.credentials:
            continue  # Unrelated optional Colab data is neither adopted nor removed.
        if _secret_exists(writer_api, enrollment.repository, "codespaces", name):
            raise CourseAccessError("An existing Codespaces access setting has no authenticated controller ownership record; it was preserved.")
    selected = {kind: value for kind, value in config.credentials.items()
                if kind in {"source", "colab"} or kind in enrollment.engines}
    for kind in enrollment.engines:
        if (kind not in selected and (kind in owned["bindings"]
                or previous[BINDING_VARIABLES[kind]])):
            raise CourseAccessError("A still-requested engine has existing or staged access but no replacement controller reader; its credentials and settings were preserved. Restore the reader or explicitly withdraw that engine.")
    if ("colab" in selected and "COLAB_OFFLOAD_DISPATCH_TOKEN" not in owned["actions"]
            and _secret_exists(writer_api, enrollment.repository, "actions", "COLAB_OFFLOAD_DISPATCH_TOKEN")):
        raise CourseAccessError("An existing Colab Actions secret has no authenticated controller ownership record; it was preserved for instructor reconciliation.")
    reader_metadata_verified = _verify_reader_metadata(app_api, config, selected)
    # Actions replacements always stage a new signed owned generation. The
    # fixed Colab label remains readable only for legacy authenticated ownership.
    binding = {BINDING_VARIABLES[kind]: "COCHEM_ACCESS_" + uuid.uuid4().hex.upper()
               for kind in selected}
    codespaces_values = {"COCHEM_ACCESS_CONTROLLER_REPOSITORY": config.repository,
                         "COCHEM_ACCESS_APP_SLUG": config.app_slug}
    if "source" in selected:
        codespaces_values["COCHEM_SOURCE_CREDENTIAL"] = selected["source"]
    if "colab" in selected:
        codespaces_values["COLAB_OFFLOAD_DISPATCH_TOKEN"] = selected["colab"]
    if len(owned["actions"]) + len(binding) > 128:
        raise CourseAccessError("Too many controller credentials await cleanup; deprovision and reconcile before re-enrollment.")
    owned["actions"] = sorted(set(owned["actions"]) | set(binding.values()))
    # Record kind ownership before any write, including the first interrupted
    # enrollment. A later missing reader must not erase a staged generation
    # simply because its student-editable selector was cleared or never saved.
    owned["bindings"] = {**owned["bindings"],
                         **{kind: binding[BINDING_VARIABLES[kind]] for kind in selected}}
    owned["codespaces"] = sorted(set(owned["codespaces"]) | codespaces_values.keys())
    owned["variables"] = sorted(_PROJECT_VARIABLES)
    owned["state"] = "staging"
    codespaces_configuration = _configure_project_codespaces(app_api, installation, read_api,
        authority_api, config, project, source_binding)
    # A canonical or config-only starter is not a final grant. Confirm the
    # atomic pair, immutable target and exact resulting HEAD before recording
    # staging ownership or delivering any credential. Later owner edits cannot
    # be made transactional with GitHub secrets; they remain a separate limit.
    current = read_api.call("GET", f"/repos/{project['full_name']}")
    if (not isinstance(current, dict) or type(current.get("id")) is not int
            or current["id"] != project["id"]
            or any(current.get(name) != project.get(name)
                   for name in ("full_name", "default_branch", "private", "archived", "fork", "owner"))):
        raise CourseAccessError("The project identity changed during Codespaces binding; no access was staged.")
    final_binding = verify_project_source(read_api, authority_api, config, current)
    if (final_binding["starter_sha"] != source_binding["starter_sha"]
            or final_binding["project_revision"] != codespaces_configuration["project_revision"]
            or _project_revision(read_api, current) != final_binding["project_revision"]):
        raise CourseAccessError("The project source changed during Codespaces binding; no access was staged.")
    source_binding = final_binding
    # Durable authenticated ownership precedes writes, so interrupted staging is
    # cleanup-safe on retry. Old readers/bindings remain in place until verified.
    _save_ownership(ledger_api, config, owned)
    pubkey = _public_key(writer_api, enrollment.repository, "actions")
    for kind, value in selected.items():
        _put_secret(writer_api, enrollment.repository, "actions", binding[BINDING_VARIABLES[kind]], value, pubkey)
    variables = {"COCHEM_APPROVED_BASE_SHA": config.approved_base_sha,
                 "COCHEM_COURSE_CHANNEL": config.course_channel,
                 **{name: binding.get(name, "") for name in BINDING_VARIABLES.values()}}
    attempted = []
    try:
        for name, value in variables.items():
            attempted.append(name)
            _write_variable(writer_api, enrollment.repository, name, value)
        if any(_variable(writer_api, enrollment.repository, name) != value for name, value in variables.items()):
            raise CourseAccessError("Project access bindings changed during provisioning; retry reconciliation.")
    except CourseAccessError:
        # Best-effort restoration cannot erase old readers. Both generations
        # stay owned until a later verified successful rotation/reconciliation.
        for name in attempted:
            try:
                if previous[name] is None:
                    try:
                        writer_api.call("DELETE", f"/repos/{enrollment.repository}/actions/variables/{name}")
                    except CourseAccessHTTPError as exc:
                        if exc.status != 404:
                            raise
                else:
                    _write_variable(writer_api, enrollment.repository, name, previous[name])
            except CourseAccessError:
                continue
        raise CourseAccessError("Project access binding replacement was incomplete; old readers and authenticated cleanup records were retained. Retry instructor reconciliation; readiness was not certified.") from None
    codespaces_key = _public_key(writer_api, enrollment.repository, "codespaces")
    for name, value in codespaces_values.items():
        _put_secret(writer_api, enrollment.repository, "codespaces", name, value, codespaces_key)
    # Recheck every binding immediately before deleting anything. There is no
    # GitHub multi-variable transaction; concurrent owner edits fail closed.
    if any(_variable(writer_api, enrollment.repository, name) != value for name, value in variables.items()):
        raise CourseAccessError("Project access bindings changed before cleanup; all readers were retained.")
    owned["bindings"] = {kind: binding[BINDING_VARIABLES[kind]] for kind in selected}
    cleanup = _cleanup_owned(writer_api, ledger_api, config, owned, actions=set(binding.values()),
                              codespaces=set(codespaces_values), state="active")
    return {"schema": RECEIPT_SCHEMA, "repository": project["full_name"], "author": author,
            "repository_id": project["id"],
            "approved_base_sha": config.approved_base_sha, **source_binding, **codespaces_configuration,
            "available": sorted(selected), "unavailable": sorted(set(enrollment.engines) - selected.keys()),
            "codespaces_source": "available" if "source" in selected else "unavailable",
            "engine_access_verified": False, "engine_execution_performed": False,
            "reader_metadata_verified": reader_metadata_verified, "asset_download_verified": False,
            "colab_access_verified": False,
            "secret_metadata_verified": True, "codespaces_secret_values_verified": False,
            "module_installation_performed": False, **cleanup,
            "status": "cleanup_pending" if cleanup["cleanup_pending"] else "provisioned",
            "timestamp_utc": datetime.now(timezone.utc).isoformat()}


def sync_calculation_access(
    writer_api: ControllerConfig,
    repository: str | EnrollmentRequest,
    *,
    author: str | None = None,
    controller_api: GitHubAPI | None = None,
    app_api: GitHubAPI | None = None,
    authority_api: GitHubAPI | None = None,
    expected_repository_id: int | None = None,
    colab_dispatch_token: str | None = None,
    orca_token: str | None = None,
    cfour_token: str | None = None,
    orca_secret_name: str = "ORCA_ASSET_READ_TOKEN",
    cfour_secret_name: str = "CFOUR_ASSET_READ_TOKEN",
    colab_secret_name: str = "COLAB_OFFLOAD_DISPATCH_TOKEN",
) -> dict[str, Any]:
    """Use the authoritative controller transaction; a writer token is not admission.

    Retained legacy keyword parameters fail explicitly instead of providing an
    alternate secret-writing path. Caller identity is never inferred from a name.
    """
    if not isinstance(writer_api, ControllerConfig):
        raise CourseAccessError("Calculation access sync requires authoritative ControllerConfig; a raw writer API is not authorization.")
    if author is None or controller_api is None:
        raise CourseAccessError("An explicit enrollment author and controller_api are required for calculation access sync.")
    if (orca_token is not None or cfour_token is not None
            or orca_secret_name != "ORCA_ASSET_READ_TOKEN"
            or cfour_secret_name != "CFOUR_ASSET_READ_TOKEN"
            or colab_secret_name != "COLAB_OFFLOAD_DISPATCH_TOKEN"):
        raise CourseAccessError("Use the authoritative controller configuration; raw readers and custom secret labels are not accepted.")
    config = writer_api
    if colab_dispatch_token is not None:
        if not isinstance(colab_dispatch_token, str) or not colab_dispatch_token.strip():
            raise CourseAccessError("The Google Colab offload dispatch token is empty or invalid.")
        supplied = colab_dispatch_token.strip()
        existing = config.credentials.get("colab")
        if existing is not None and existing != supplied:
            raise CourseAccessError("The supplied Colab token conflicts with the authoritative controller configuration; existing access was preserved.")
        if existing is None:
            config = replace(config, credentials={**config.credentials, "colab": supplied})
    enrollment = (repository if isinstance(repository, EnrollmentRequest)
                  else EnrollmentRequest(str(repository), ("orca", "cfour")))
    return provision_project(config, enrollment, author=author,
        controller_api=controller_api, app_api=app_api, authority_api=authority_api,
        expected_repository_id=expected_repository_id)


def deprovision_project(config: ControllerConfig, repository: str, *,
                        controller_api: GitHubAPI, app_api: GitHubAPI | None = None,
                        expected_repository_id: int | None = None) -> dict[str, Any]:
    """Withdraw controller-owned stores without touching source or student data.

    Removal from the team does not prevent cleanup. An uninstalled App cannot
    delete secrets; that API failure remains a blocker, never a success receipt.
    """
    enrollment = EnrollmentRequest(repository, ())
    app_api, installation, _, project = _project_context(config, enrollment,
        author=repository.split("/")[0], controller_api=controller_api,
        app_api=app_api, require_membership=False, require_active_project=False)
    if expected_repository_id is not None and (type(expected_repository_id) is not int
            or expected_repository_id <= 0 or project["id"] != expected_repository_id):
        raise CourseAccessError("The project immutable identity changed after the inbox hold check; no project access was written.")
    api = _project_writer(app_api, installation, project)
    ledger_api = _controller_ledger_api(app_api, config)
    owned = _ownership(ledger_api, config, project)
    if owned["state"] == "new":
        raise CourseAccessError("No authenticated controller ownership record exists; existing student settings were preserved.")
    owned["state"] = "revoking"
    _save_ownership(ledger_api, config, owned)
    # Clear and verify selectors first. Any failure retains every credential and
    # the revoking state; the next revoke/reconcile call resumes safely.
    for name in owned["variables"]:
        _write_variable(api, repository, name, "")
    if any(_variable(api, repository, name) != "" for name in owned["variables"]):
        raise CourseAccessError("Project withdrawal bindings could not be confirmed; cleanup remains pending.")
    owned["bindings"] = {}
    cleanup = _cleanup_owned(api, ledger_api, config, owned, actions=set(), codespaces=set(), state="revoked")
    return {"schema": RECEIPT_SCHEMA, "repository": project["full_name"],
            "repository_id": project["id"], "status": "cleanup_pending" if cleanup["cleanup_pending"] else "deprovisioned",
            "available": [], **cleanup, "engine_execution_performed": False,
            "timestamp_utc": datetime.now(timezone.utc).isoformat()}


def reconcile_project(config: ControllerConfig, enrollment: EnrollmentRequest, *,
                      controller_api: GitHubAPI, app_api: GitHubAPI | None = None,
                      authority_api: GitHubAPI | None = None,
                      expected_repository_id: int | None = None) -> dict[str, Any]:
    """Recheck live membership; removed members can only have access withdrawn."""
    author = enrollment.repository.split("/")[0]
    app_api = app_api or GitHubAPI(app_jwt(config.app_id, config.private_key))
    if not _active_member(app_api, config, author):
        return deprovision_project(config, enrollment.repository, controller_api=controller_api, app_api=app_api,
                                   expected_repository_id=expected_repository_id)
    return provision_project(config, enrollment, author=author, controller_api=controller_api,
                             app_api=app_api, authority_api=authority_api,
                             expected_repository_id=expected_repository_id)
