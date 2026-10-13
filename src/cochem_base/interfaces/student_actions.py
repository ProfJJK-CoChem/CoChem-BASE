"""Authenticated, no-code submission and retrieval for student calculations.

Small scientific inputs are data-only workflow-dispatch inputs. Larger native
evidence is stored automatically on an isolated data branch. No student source
file is edited. Long-running methods are suitable for a GUI background worker;
status polling does not wait for calculation completion.
"""
from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .student_request import (
    COMMIT_PATTERN,
    REPOSITORY_PATTERN,
    SHA_PATTERN,
    canonical_json,
    encode_request,
    safe_relative_path,
    strict_json,
)

WORKFLOW = "student_research.yml"
SETUP_WORKFLOW = "student_project_setup.yml"
SETUP_RUN_PREFIX = "CoChem setup "
MAX_SETUP_BYTES = 64 * 1024
CANONICAL_BASE = "ProfJJK-CoChem/CoChem-BASE"
RUN_PREFIX = "CoChem student "
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_EXTRACTED_BYTES = 512 * 1024 * 1024
MAX_ARCHIVE_FILES = 4096


class StudentActionsError(RuntimeError):
    """An actionable authorization, execution or result-integrity failure."""

    def __init__(self, message: str, *, http_status: int | None = None, uncertain: bool = False):
        super().__init__(message)
        self.http_status = http_status
        self.uncertain = uncertain
        self.submission: dict | None = None
        self.setup_url: str | None = None
        self.project_access: dict[str, bool] | None = None


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def _read_bounded(stream, maximum: int) -> bytes:
    contents = stream.read(maximum + 1)
    if len(contents) > maximum:
        raise StudentActionsError("The GitHub response exceeds the permitted download size")
    return contents


def _credential(explicit: str | None) -> str:
    if explicit is not None:
        token = explicit.strip()
    else:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            try:
                completed = subprocess.run(["gh", "auth", "token", "--hostname", "github.com"],
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL, timeout=15, check=False,
                                           text=True)
            except (OSError, subprocess.SubprocessError):
                completed = None
            token = completed.stdout.strip() if completed and completed.returncode == 0 else ""
    if not token or any(char.isspace() for char in token):
        raise StudentActionsError("GitHub authentication is unavailable. Authorize GitHub in BASE before submitting.")
    return token


def _verify_result_directory(directory: Path, submission: dict, run: dict) -> dict:
    """Use one verifier for newly downloaded and retained scientific evidence."""
    members = list(directory.rglob("*"))
    if len(members) > MAX_ARCHIVE_FILES:
        raise StudentActionsError("The retained results exceed their bounded file count")
    total = 0
    for path in members:
        safe_relative_path(path.relative_to(directory).as_posix())
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise StudentActionsError("Retained results cannot contain links or special files")
        if path.is_file():
            total += path.stat().st_size
    if total > MAX_EXTRACTED_BYTES:
        raise StudentActionsError("The retained results exceed their expanded size limit")
    manifest = strict_json((directory / "publication-manifest.json").read_bytes())
    report = strict_json((directory / "student-result.json").read_bytes())
    expected = {"request_id": submission["request_id"], "repository": submission["repository"],
                "source_sha": submission["source_sha"], "worker_source_sha": submission["worker_source_sha"],
                "payload_sha256": submission["payload_sha256"],
                "run_id": run["run_id"], "run_attempt": run["run_attempt"]}
    if (manifest.get("schema_version") != "cochem.student-publication/1"
            or any(manifest.get(key) != value or report.get(key) != value for key, value in expected.items())):
        raise StudentActionsError("Result provenance differs from the submitted request or exact GitHub run")
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise StudentActionsError("The results have no complete file inventory")
    actual = {path.relative_to(directory).as_posix() for path in members if path.is_file()}
    if actual != set(files) | {"publication-manifest.json"}:
        raise StudentActionsError("Unlisted or missing files in the results")
    for name, identity in files.items():
        safe_relative_path(name)
        path = directory / name
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if not isinstance(identity, dict) or identity != {"sha256": digest, "size_bytes": path.stat().st_size}:
            raise StudentActionsError(f"Downloaded result integrity failed: {name}")
    original = strict_json((directory / "request.json").read_bytes())
    if (hashlib.sha256(canonical_json(original)).hexdigest() != submission["payload_sha256"]
            or original.get("request_id") != submission["request_id"]):
        raise StudentActionsError("Downloaded input differs from the original submitted bytes")
    if report.get("status") == "completed":
        approved = strict_json((directory / "worker-approval.json").read_bytes())
        source = strict_json((directory / "worker-source.json").read_bytes())
        catalog = (directory / "worker-module-distribution.json").read_bytes()
        performed = (report.get("capability_probe_performed") is True
                     if original.get("capability_probe") is not None else report.get("operation_performed") is True)
        if (not performed
                or approved.get("worker_source_sha") != submission["worker_source_sha"]
                or approved.get("assignment_source_sha") != submission["source_sha"]
                or source.get("worker_source_sha") != submission["worker_source_sha"]
                or source.get("module_manifest_sha256") != hashlib.sha256(catalog).hexdigest()):
            raise StudentActionsError("Completed science lacks its approved worker and exact ecosystem catalog proof")
    return {"path": str(directory), "report": report, "files": sorted(actual),
            "request_id": submission["request_id"], "run_id": run["run_id"]}


def verify_retained_results(directory: Path, submission: dict) -> dict:
    """Reopen sealed local results without GitHub or artifact retention access.

    The persisted receipt must include the exact run ID and run attempt. This
    verifies data integrity and attribution; it never executes artifact code.
    """
    directory = Path(directory).expanduser().absolute()
    if (directory.is_symlink() or not directory.is_dir()
            or directory.resolve().is_relative_to(Path(__file__).resolve().parents[3])):
        raise StudentActionsError("Select retained results outside the BASE source checkout")
    try:
        if any(type(submission.get(key)) is not int or submission[key] < 1 for key in ("run_id", "run_attempt")):
            raise StudentActionsError("Retained results need the exact original GitHub run and attempt receipt")
        return _verify_result_directory(directory, submission, submission)
    except (OSError, KeyError, ValueError, TypeError):
        raise StudentActionsError("Retained results failed complete verification; no scientific data was imported") from None


def _extract_verified_archive(contents: bytes, destination: Path, submission: dict,
                              run: dict) -> dict:
    """Validate the complete ZIP before making any downloaded file visible."""
    if len(contents) > MAX_ARCHIVE_BYTES:
        raise StudentActionsError("The result archive exceeds the 100 MiB download limit")
    destination = destination.expanduser().absolute()
    # Runtime results must never overwrite the installed/source application.
    repository = Path(__file__).resolve().parents[3]
    if destination.resolve().is_relative_to(repository):
        raise StudentActionsError("Choose a results directory outside the BASE source checkout")
    if destination.exists() or destination.is_symlink():
        raise StudentActionsError("Choose a new results directory; existing files will not be replaced")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".cochem-result-", dir=destination.parent))
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            members = archive.infolist()
            if len(members) > MAX_ARCHIVE_FILES or sum(item.file_size for item in members) > MAX_EXTRACTED_BYTES:
                raise StudentActionsError("The result archive exceeds its bounded file count or expanded size")
            seen: set[str] = set()
            for item in members:
                name = item.filename.rstrip("/") if item.is_dir() else item.filename
                safe_relative_path(name)
                if name in seen:
                    raise StudentActionsError("Duplicate result archive path")
                seen.add(name)
                mode = item.external_attr >> 16
                if (stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
                        or item.flag_bits & 1
                        or item.file_size > MAX_EXTRACTED_BYTES
                        or item.file_size > max(item.compress_size, 1) * 1000):
                    raise StudentActionsError("Result archives cannot contain links, special files, encryption or oversized compression")
            for item in members:
                target = staging / item.filename
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as source, target.open("xb") as output:
                        shutil.copyfileobj(source, output)
                    target.chmod(0o600)
        result = _verify_result_directory(staging, submission, run)
        os.rename(staging, destination)
        return {**result, "path": str(destination)}
    except (OSError, KeyError, ValueError, TypeError, zipfile.BadZipFile):
        raise StudentActionsError("The result archive failed complete validation; no files were imported") from None
    finally:
        if staging.exists():
            shutil.rmtree(staging)


class StudentActionsClient:
    """Use the student's GitHub identity; keep source-reader secrets in Actions."""

    def __init__(self, repository: str, branch: str | None = None, token: str | None = None, *,
                 repository_root: Path | None = None, artifact_dir: Path | None = None,
                 api_url: str = "https://api.github.com", allow_loopback: bool = False):
        if not isinstance(repository, str) or not REPOSITORY_PATTERN.fullmatch(repository):
            raise ValueError("Select your GitHub project using its account/project name")
        parsed = urllib.parse.urlsplit(api_url)
        local_test = (allow_loopback and parsed.scheme == "http"
                      and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
                      and not parsed.username and not parsed.password and not parsed.query
                      and not parsed.fragment and not parsed.path)
        if api_url != "https://api.github.com" and not local_test:
            raise ValueError("Student access uses GitHub's verified HTTPS API")
        self.repository = repository
        self.branch = branch
        self.repository_root = Path(repository_root or Path.cwd()).expanduser().resolve()
        self.artifact_dir = artifact_dir
        self._api_url = api_url
        self._token = _credential(token)
        self._opener = urllib.request.build_opener(_NoRedirect())

    def _request(self, path: str, *, method: str = "GET", body: dict | None = None,
                 binary: bool = False, maximum_bytes: int | None = None):
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("GitHub API paths must be relative to api.github.com")
        request = urllib.request.Request(self._api_url + path,
            data=canonical_json(body) if body is not None else None, method=method,
            headers={"Authorization": "Bearer " + self._token, "Accept": "application/vnd.github+json",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "CoChem-BASE-student-actions",
                     "Content-Type": "application/json"})
        limit = maximum_bytes if maximum_bytes is not None else (MAX_ARCHIVE_BYTES if binary else 4 * 1024 * 1024)
        try:
            with self._opener.open(request, timeout=30) as response:
                contents = _read_bounded(response, limit)
                return contents if binary else strict_json(contents) if contents else {}
        except urllib.error.HTTPError as error:
            if binary and error.code == 302:
                location = error.headers.get("Location", "")
                parsed = urllib.parse.urlparse(location)
                host = (parsed.hostname or "").lower()
                if (parsed.scheme != "https" or parsed.username or parsed.password
                        or parsed.port not in (None, 443)
                        or not host.endswith((".blob.core.windows.net", ".githubusercontent.com",
                                              ".actions.githubusercontent.com", ".amazonaws.com"))):
                    raise StudentActionsError("GitHub returned an unapproved artifact download destination") from None
                # The signed storage URL is fetched without the GitHub credential.
                download = urllib.request.Request(location, headers={"User-Agent": "CoChem-BASE-student-actions"})
                try:
                    with self._opener.open(download, timeout=60) as response:
                        return _read_bounded(response, limit)
                except (urllib.error.URLError, OSError):
                    raise StudentActionsError("The result download failed; retry from the completed run") from None
            if error.code in (401, 403):
                refused = StudentActionsError(
                    f"GitHub has not allowed this Codespace to start or read jobs in {self.repository}. "
                    "Create a new Codespace for this project and approve the requested GitHub Actions permissions. "
                    "Rebuilding the existing Codespace does not refresh those permissions. "
                    "If no permission request appears, ask your instructor to update the project's Codespaces setup.",
                    http_status=error.code)
                refused.setup_url = f"https://github.com/{CANONICAL_BASE}/blob/main/.docs/Student_Research_No_Code.md"
                raise refused from None
            if error.code == 404:
                raise StudentActionsError("GitHub could not find this project, calculation workflow or result for your account",
                                          http_status=error.code) from None
            raise StudentActionsError(f"GitHub could not complete the request (HTTP {error.code})",
                                      http_status=error.code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise StudentActionsError("GitHub could not be reached. Check this submission before creating another.",
                                      uncertain=method == "POST") from None
        except (ValueError, UnicodeError):
            raise StudentActionsError("GitHub returned an invalid acknowledgement. Check the original submission before retrying.",
                                      uncertain=method == "POST") from None

    def _persist_submission(self, submission: dict) -> None:
        root = Path(self.artifact_dir or os.environ.get("COCHEM_ARTIFACT_DIR", "~/CoChem_Artifacts")).expanduser().resolve()
        if root.is_relative_to(self.repository_root):
            raise StudentActionsError("Submission records must remain outside the student source checkout")
        destination = root / "StudentActions" / "submissions"
        if any(path.is_symlink() for path in (root / "StudentActions", destination)):
            raise StudentActionsError("Submission records cannot use redirected runtime directories")
        destination.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, temporary = tempfile.mkstemp(prefix=".submission-", dir=destination)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(canonical_json(submission) + b"\n")
            os.replace(temporary, destination / (submission["request_id"] + ".json"))
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def preflight(self) -> dict:
        repo = self._request(f"/repos/{self.repository}")
        branch = repo["default_branch"]
        if self.branch is not None and self.branch != branch:
            raise StudentActionsError("Select this project's main working branch before submitting calculations")
        if repo.get("archived") or repo.get("disabled"):
            raise StudentActionsError("This project is archived or disabled; its owner must reopen it before running jobs")
        permissions = repo.get("permissions", {})
        if permissions and not any(permissions.get(key) for key in ("push", "maintain", "admin")):
            raise StudentActionsError("Ask the project owner to give your GitHub account Write access so you can submit jobs")
        workflow = self._request(f"/repos/{self.repository}/actions/workflows/{WORKFLOW}")
        if workflow.get("state") != "active":
            raise StudentActionsError("The student calculation workflow must be enabled by the instructor")
        commit = self._request(f"/repos/{self.repository}/commits/{urllib.parse.quote(branch, safe='')}")
        if not COMMIT_PATTERN.fullmatch(commit.get("sha", "")):
            raise StudentActionsError("GitHub did not return an exact assignment source commit")
        setup = self._project_setup(branch=branch, source_sha=commit["sha"])
        try:
            worker = self._resolve_worker_source(setup)
        except StudentActionsError as exc:
            exc.project_access = setup["access"]
            exc.setup_url = exc.setup_url or setup["url"]
            raise
        return {"repository": self.repository, "branch": branch, "source_sha": commit["sha"],
                "worker_source_sha": worker["revision"], "worker_approval": worker["approval"],
                "project_access": setup["access"], "setup_check_url": setup["url"],
                "workflow_id": workflow["id"], "workflow_ready": True,
                "actions_write_permission": "not_yet_verified",
                "secret_inspection_required": False, "student_source_commit_required": False}

    def _project_setup(self, *, branch: str, source_sha: str) -> dict:
        """Read project settings through Actions, which a Codespace can authorize.

        This check discloses only version selections and credential-presence
        booleans. It does not install an engine or authorize a scientific result.
        The calculation worker rechecks its current settings before execution.
        """
        setup_url = f"https://github.com/{self.repository}/actions/workflows/{SETUP_WORKFLOW}"
        try:
            workflow = self._request(f"/repos/{self.repository}/actions/workflows/{SETUP_WORKFLOW}")
        except StudentActionsError as exc:
            if exc.http_status == 404:
                error = StudentActionsError(
                    "This project is missing the current CoChem setup workflow. Ask the instructor to update "
                    "the CoChem workflow files in this project's repository, then check GitHub Actions again. "
                    "'Check for updates' updates the interface but does not change those project files.",
                    http_status=404)
                error.setup_url = f"https://github.com/{CANONICAL_BASE}#readme"
                raise error from None
            raise
        if (not isinstance(workflow, dict) or workflow.get("state") != "active" or type(workflow.get("id")) is not int
                or workflow["id"] < 1
                or workflow.get("path") != ".github/workflows/" + SETUP_WORKFLOW):
            error = StudentActionsError(
                "The project's setup check is unavailable. Open its GitHub Actions page and enable "
                "'CoChem project setup check', then try again.")
            error.setup_url = setup_url
            raise error
        request_id = str(uuid.uuid4())
        created = datetime.now(timezone.utc) - timedelta(seconds=30)
        query = urllib.parse.quote(">=" + created.strftime("%Y-%m-%dT%H:%M:%SZ"), safe="")
        try:
            self._request(f"/repos/{self.repository}/actions/workflows/{workflow['id']}/dispatches",
                          method="POST", body={"ref": branch, "inputs": {"request_id": request_id}})
        except StudentActionsError as exc:
            if not exc.uncertain:
                exc.setup_url = setup_url
                raise
            # A lost response can follow a successful dispatch. Look up this
            # exact check before declaring it unavailable; never POST it twice.
        deadline = time.monotonic() + 180
        while True:
            matches = []
            for page in range(1, 6):
                listing = self._request(f"/repos/{self.repository}/actions/workflows/{workflow['id']}/runs"
                    f"?event=workflow_dispatch&created={query}&per_page=100&page={page}")
                if (not isinstance(listing, dict) or not isinstance(listing.get("workflow_runs"), list)
                        or any(not isinstance(run, dict) for run in listing["workflow_runs"])):
                    raise StudentActionsError("GitHub returned an invalid setup-check status. No calculation was submitted.")
                matches.extend(run for run in listing["workflow_runs"]
                               if run.get("display_title") == SETUP_RUN_PREFIX + request_id)
                if len(listing["workflow_runs"]) < 100:
                    break
            if len(matches) > 1:
                raise StudentActionsError("GitHub returned duplicate setup checks. No calculation was submitted.")
            if matches:
                run = matches[0]
                if (run.get("event") != "workflow_dispatch" or run.get("head_sha") != source_sha
                        or run.get("head_branch") != branch or run.get("workflow_id") != workflow["id"]
                        or type(run.get("id")) is not int or run["id"] < 1
                        or type(run.get("run_attempt")) is not int or run["run_attempt"] < 1):
                    raise StudentActionsError(
                        "The project changed while GitHub checked its setup. Check GitHub Actions again; "
                        "your structures have been kept.")
                setup_url = f"https://github.com/{self.repository}/actions/runs/{run['id']}"
                if run.get("status") == "completed":
                    if run.get("conclusion") != "success":
                        error = StudentActionsError(
                            "GitHub could not finish the project setup check. Open the check's result "
                            "and ask the instructor to correct the reported setup problem. No calculation was submitted.")
                        error.setup_url = setup_url
                        raise error
                    return {**self._setup_artifact(request_id, source_sha, run), "url": setup_url}
            if time.monotonic() >= deadline:
                error = StudentActionsError(
                    "GitHub is still checking this project's setup. Open the check's progress, then try again "
                    "after it finishes. No calculation was submitted; your structures have been kept.")
                error.setup_url = setup_url
                raise error
            time.sleep(min(2, max(0, deadline - time.monotonic())))

    def _setup_artifact(self, request_id: str, source_sha: str, run: dict) -> dict:
        listing = self._request(f"/repos/{self.repository}/actions/runs/{run['id']}/artifacts?per_page=100")
        name = f"cochem-setup-{request_id}-{run['id']}-{run['run_attempt']}"
        matches = [entry for entry in listing.get("artifacts", []) if entry.get("name") == name]
        if (len(matches) != 1 or matches[0].get("expired") is not False
                or type(matches[0].get("id")) is not int or matches[0]["id"] < 1
                or type(matches[0].get("size_in_bytes")) is not int
                or not 0 < matches[0]["size_in_bytes"] <= MAX_SETUP_BYTES):
            raise StudentActionsError("GitHub did not provide a complete setup-check result. Check the project again.")
        artifact = matches[0]
        contents = self._request(f"/repos/{self.repository}/actions/artifacts/{artifact['id']}/zip",
                                 binary=True, maximum_bytes=MAX_SETUP_BYTES)
        if (len(contents) > MAX_SETUP_BYTES
                or artifact.get("digest") != "sha256:" + hashlib.sha256(contents).hexdigest()):
            raise StudentActionsError("The setup-check download failed its integrity check. No calculation was submitted.")
        try:
            with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                entries = archive.infolist()
                if (len(entries) != 1 or entries[0].filename != "project-setup.json"
                        or entries[0].is_dir() or entries[0].flag_bits & 1
                        or stat.S_IFMT(entries[0].external_attr >> 16) not in (0, stat.S_IFREG)
                        or entries[0].file_size > MAX_SETUP_BYTES):
                    raise ValueError("Unexpected setup archive")
                metadata = strict_json(archive.read(entries[0]))
            identity = {"schema_version": "cochem.project-setup/1", "request_id": request_id,
                        "repository": self.repository, "source_sha": source_sha,
                        "run_id": run["id"], "run_attempt": run["run_attempt"]}
            if (not isinstance(metadata, dict)
                    or set(metadata) != {*identity, "approved_base_sha", "course_channel", "access"}
                    or any(metadata.get(key) != value for key, value in identity.items())
                    or type(metadata["run_id"]) is not int or type(metadata["run_attempt"]) is not int
                    or not isinstance(metadata["approved_base_sha"], str)
                    or not isinstance(metadata["course_channel"], str)
                    or not isinstance(metadata["access"], dict)
                    or set(metadata["access"]) != {"source", "orca", "cfour"}
                    or any(type(value) is not bool for value in metadata["access"].values())):
                raise ValueError("Mismatched setup identity")
        except (ValueError, TypeError, KeyError, UnicodeError, zipfile.BadZipFile):
            raise StudentActionsError(
                "The setup-check result is invalid or does not match this project and GitHub run. "
                "No calculation was submitted; check the project again.") from None
        return metadata

    def _resolve_worker_source(self, setup: dict) -> dict:
        """Student work stays in its repository; science comes from approved BASE."""
        from .student_setup import resolve_worker_source
        # The check reads current protected settings inside Actions. The normal
        # Codespaces identity needs no separate Variables API permission.
        resolved = self._project_worker_approval(setup)
        if resolved is None:
            resolved = resolve_worker_source(repository_root=self.repository_root, artifact_dir=self.artifact_dir,
                                             token=self._token)
        # A missing worker in a frozen course/stable revision must never silently
        # switch that student's scientific version to a different revision.
        try:
            self._request(f"/repos/{CANONICAL_BASE}/contents/scripts/run_student_research.py"
                          f"?ref={resolved['revision']}")
        except StudentActionsError:
            raise StudentActionsError(
                "The BASE version selected for this project cannot run student calculations or could not be read. "
                "Ask the instructor to update the project's BASE version and access. Your structures have been kept.") from None
        if not COMMIT_PATTERN.fullmatch(resolved.get("revision", "")):
            raise StudentActionsError("GitHub could not verify the exact BASE version selected for this project")
        return resolved

    def _project_worker_approval(self, setup: dict) -> dict | None:
        """Resolve the software version selected by the instructor's settings."""
        revision = setup["approved_base_sha"]
        if revision:
            if not COMMIT_PATTERN.fullmatch(revision):
                raise StudentActionsError("This project's selected BASE version is invalid. Ask the instructor to correct its version setting.")
            approval = "instructor-actions-variable"
            label = "Instructor-approved BASE " + revision[:12]
        else:
            channel = setup["course_channel"]
            if not channel:
                return None
            if not re.fullmatch(r"\.cochem/course-channels/[a-z0-9][a-z0-9_-]*\.json", channel):
                raise StudentActionsError("The project's update setting must name a BASE version file published by the instructor")
            document = self._request(f"/repos/{CANONICAL_BASE}/contents/{channel}")
            if (not isinstance(document, dict) or document.get("type") != "file"
                    or document.get("encoding") != "base64"
                    or not isinstance(document.get("content"), str)):
                raise StudentActionsError("The instructor's BASE version file could not be read. Ask them to check the project's update setting.")
            try:
                course = strict_json(base64.b64decode(document["content"], validate=False))
            except (ValueError, TypeError):
                raise StudentActionsError("The instructor's BASE version file is invalid. Ask them to correct it.") from None
            if (not isinstance(course, dict) or course.get("schema_version") != "cochem.course-approval/1"
                    or course.get("repository", CANONICAL_BASE) != CANONICAL_BASE
                    or not COMMIT_PATTERN.fullmatch(str(course.get("approved_base_revision", "")))):
                raise StudentActionsError("The instructor's version file does not select an exact BASE version")
            revision = course["approved_base_revision"]
            approval = "instructor-course-channel"
            label = "Instructor course channel " + channel
        commit = self._request(f"/repos/{CANONICAL_BASE}/commits/{revision}")
        if not isinstance(commit, dict) or commit.get("sha") != revision:
            raise StudentActionsError("GitHub could not verify this project's selected BASE version. Ask the instructor to check its update setting.")
        return {"revision": revision, "approval": approval, "label": label, "repository": CANONICAL_BASE}

    def submit(self, calculation: dict | None, *, xyz_files: dict[str, str | bytes] | None = None,
               provider: dict | None = None, capability_probe: dict | None = None,
               scientific_inputs: dict | None = None, t9_request: dict | None = None,
               ingestion_inputs: dict | None = None, periodic_inputs: dict | None = None,
               cores: int = 2, maxcore_mb: int = 512) -> dict:
        prepared = self.preflight()
        # Licensed engines and private modules are independent options. Public
        # BASE/free-engine jobs need only the job's ordinary GitHub token.
        missing = []
        if provider is not None and not prepared["project_access"]["source"]:
            missing.append("TOPOS/TORQ module access")
        if capability_probe is None:
            if provider is not None:
                from .student_research import required_provider_engines
                engines = required_provider_engines(provider)
            else:
                engines = [calculation.get("engine")] if isinstance(calculation, dict) else []
            missing.extend(engine.upper() + " access" for engine in engines
                           if engine in {"orca", "cfour"} and not prepared["project_access"][engine])
        if missing:
            error = StudentActionsError(
                "This project has not been given " + ", ".join(missing) + ". "
                "Use the lab access controls in BASE, or ask the instructor to connect this project, "
                "then check GitHub Actions again. Your structures have been kept.")
            error.setup_url = prepared["setup_check_url"]
            error.project_access = prepared["project_access"]
            raise error
        files = {}
        for name, value in (xyz_files or {}).items():
            contents = value.encode("utf-8") if isinstance(value, str) else bytes(value)
            files[name] = {"content_base64": base64.b64encode(contents).decode("ascii"),
                           "sha256": hashlib.sha256(contents).hexdigest(), "size_bytes": len(contents)}
        request_id = str(uuid.uuid4())
        submitted_at = datetime.now(timezone.utc).isoformat()
        scientific_descriptor = None
        data_descriptor = None
        if ingestion_inputs is not None and periodic_inputs is not None:
            raise ValueError("Select a molecular source or a periodic PAW source for this job")
        if ingestion_inputs is not None or periodic_inputs is not None:
            from copy import deepcopy

            from .student_data_inputs import build_data_bundle
            from .student_input_transport import upload_blob_bundle
            if periodic_inputs is not None:
                if calculation is None or calculation.get("engine") != "qe":
                    raise ValueError("Periodic PAW inputs require a QE calculation")
                calculation = deepcopy(calculation)
                calculation["periodic"]["pseudopotentials"] = {
                    element: {"path": "pseudopotentials/" + element + ".UPF", "sha256": entry["sha256"]}
                    for element, entry in periodic_inputs["pseudopotentials"].items()}
            geometry = (calculation["geometry"].encode("utf-8") if calculation is not None else
                        base64.b64decode(files[provider["artifact"]]["content_base64"], validate=True))
            contents, metadata = build_data_bundle(periodic_inputs if periodic_inputs is not None else ingestion_inputs,
                kind="periodic_inputs" if periodic_inputs is not None else "molecular_ingestion",
                request_id=request_id, geometry_sha256=hashlib.sha256(geometry).hexdigest())
            data_descriptor = upload_blob_bundle(self, contents, metadata, request_id=request_id,
                assignment_sha=prepared["source_sha"], filename="data-inputs.zip",
                schema_version="cochem.student-data-transport/1")
        if scientific_inputs is not None:
            if calculation is None:
                raise ValueError("Reference/Hessian inputs belong to an explicit calculation")
            from .student_input_transport import upload_scientific_inputs
            scientific_descriptor = upload_scientific_inputs(self, scientific_inputs, request_id=request_id,
                geometry_xyz=calculation["geometry"], assignment_sha=prepared["source_sha"])
        request = {"schema_version": "cochem.student-request/1", "request_id": request_id,
                   "repository": self.repository, "source_sha": prepared["source_sha"],
                   "worker_source_sha": prepared["worker_source_sha"],
                   "submitted_at": submitted_at, "resources": {"cores": cores, "maxcore_mb": maxcore_mb},
                   "calculation": calculation, "provider": provider, "capability_probe": capability_probe, "files": files}
        request.update(scientific_inputs=scientific_descriptor, data_inputs=data_descriptor, t9_request=t9_request)
        if provider is not None:
            from .student_research import validate_provider_request
            validate_provider_request(provider, files)
        encoded, digest = encode_request(request)
        submission = {"request_id": request_id, "repository": self.repository, "branch": prepared["branch"],
                "source_sha": prepared["source_sha"], "workflow_id": prepared["workflow_id"],
                "worker_source_sha": prepared["worker_source_sha"],
                "payload_sha256": digest, "submitted_at": submitted_at, "run_id": None,
                "url": f"https://github.com/{self.repository}/actions", "status": "prepared"}
        submission["request_kind"] = ("capability_probe" if capability_probe is not None
                                      else "provider" if provider is not None else "calculation")
        # Save correlation identity before the POST. A lost acknowledgement must
        # never turn a successfully accepted request into a blind duplicate.
        self._persist_submission(submission)
        try:
            self._request(f"/repos/{self.repository}/actions/workflows/{prepared['workflow_id']}/dispatches",
                          method="POST", body={"ref": prepared["branch"], "inputs": {
                              "request_id": request_id, "request_sha256": digest, "request_base64": encoded}})
        except StudentActionsError as error:
            submission.update(status="dispatch_unconfirmed" if error.uncertain else "rejected", error=str(error))
            error.submission = submission
            try:
                self._persist_submission(submission)
            except (OSError, StudentActionsError):
                submission["record_warning"] = "The initial submission identity is retained; its latest status could not be saved."
            if not error.uncertain:
                raise
        else:
            submission["status"] = "dispatching"
            try:
                self._persist_submission(submission)
            except (OSError, StudentActionsError):
                submission["record_warning"] = "GitHub accepted the request. Its initial identity is retained; check this request's status."
        return submission

    def check_engines(self, engines: list[str] | None = None) -> dict:
        """Probe access through protected Actions secrets, never list their names."""
        return self.submit(None, capability_probe={"engines": engines or ["orca", "cfour"]},
                           cores=1, maxcore_mb=128)

    def _validate_run(self, submission: dict, run: dict) -> dict:
        if (submission.get("repository") != self.repository
                or run.get("display_title") != RUN_PREFIX + submission["request_id"]
                or run.get("event") != "workflow_dispatch" or run.get("head_sha") != submission["source_sha"]
                or run.get("workflow_id") != submission["workflow_id"]
                or run.get("head_branch") != submission["branch"]):
            raise StudentActionsError("GitHub run identity does not match this submitted calculation")
        return {**submission, "run_id": run["id"], "run_attempt": run.get("run_attempt", 1),
                "status": run["status"], "conclusion": run.get("conclusion"), "url": run["html_url"],
                "artifact_name": f"cochem-student-{submission['request_id']}-{run['id']}-{run.get('run_attempt', 1)}"}

    def _validate_submission(self, submission: dict) -> None:
        try:
            valid = (submission["repository"] == self.repository
                     and str(uuid.UUID(submission["request_id"])) == submission["request_id"]
                     and COMMIT_PATTERN.fullmatch(submission["source_sha"])
                     and COMMIT_PATTERN.fullmatch(submission["worker_source_sha"])
                     and SHA_PATTERN.fullmatch(submission["payload_sha256"])
                     and type(submission["workflow_id"]) is int and submission["workflow_id"] > 0
                     and isinstance(submission["branch"], str)
                     and bool(submission["branch"])
                     and (submission.get("run_id") is None or (type(submission["run_id"]) is int
                                                               and submission["run_id"] > 0)))
            created = datetime.fromisoformat(submission["submitted_at"])
            valid = valid and created.tzinfo is not None
        except (KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise StudentActionsError("The saved submission identity is invalid; select an intact BASE submission record")

    def status(self, submission: dict) -> dict:
        self._validate_submission(submission)
        if submission.get("run_id") is not None:
            current = self._validate_run(submission, self._request(
                f"/repos/{self.repository}/actions/runs/{int(submission['run_id'])}"))
            self._persist_submission(current)
            return current
        matches = []
        created = datetime.fromisoformat(submission["submitted_at"]).astimezone(timezone.utc) - timedelta(seconds=30)
        created_query = urllib.parse.quote(">=" + created.strftime("%Y-%m-%dT%H:%M:%SZ"), safe="")
        for page in range(1, 6):
            result = self._request(f"/repos/{self.repository}/actions/workflows/{submission['workflow_id']}/runs"
                                   f"?event=workflow_dispatch&created={created_query}&per_page=100&page={page}")
            runs = result.get("workflow_runs", [])
            matches.extend(run for run in runs if run.get("display_title") == RUN_PREFIX + submission["request_id"])
            if len(runs) < 100:
                break
        if len(matches) > 1:
            raise StudentActionsError("Duplicate request identities were dispatched; select the exact run for instructor review")
        current = self._validate_run(submission, matches[0]) if matches else {
            **submission, "status": "dispatch_unconfirmed" if submission.get("status") == "dispatch_unconfirmed" else "dispatching",
            "conclusion": None}
        self._persist_submission(current)
        return current

    def cancel(self, submission: dict) -> dict:
        current = self.status(submission)
        if current.get("run_id") is None:
            raise StudentActionsError("GitHub has not registered this run yet; retry cancellation shortly")
        if current["status"] == "completed":
            return current
        self._request(f"/repos/{self.repository}/actions/runs/{current['run_id']}/cancel", method="POST")
        return {**current, "status": "cancellation_requested"}

    def download_results(self, submission: dict, destination: Path) -> dict:
        current = self.status(submission)
        if current["status"] != "completed":
            raise StudentActionsError("Results become available when the exact calculation run completes")
        result = self._request(f"/repos/{self.repository}/actions/runs/{current['run_id']}/artifacts?per_page=100")
        artifacts = [item for item in result.get("artifacts", []) if item["name"] == current["artifact_name"]]
        if len(artifacts) != 1 or artifacts[0].get("expired"):
            raise StudentActionsError("This run's result artifact is unavailable or expired; retained artifacts last fourteen days")
        artifact = artifacts[0]
        if artifact.get("size_in_bytes", 0) > MAX_ARCHIVE_BYTES:
            raise StudentActionsError("This result exceeds the bounded browser download limit")
        contents = self._request(f"/repos/{self.repository}/actions/artifacts/{artifact['id']}/zip", binary=True)
        digest = artifact.get("digest")
        if digest is not None and digest != "sha256:" + hashlib.sha256(contents).hexdigest():
            raise StudentActionsError("The downloaded ZIP differs from GitHub's artifact SHA-256")
        return _extract_verified_archive(contents, destination, submission, current)
