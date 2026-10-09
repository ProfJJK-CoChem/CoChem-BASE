"""Queue student calculations to a lab workstation through a Drive folder the user assigns.

The workstation runs the CoChem workstation job runner
(https://github.com/ProfJJK-CoChem/cochem_workstation_job_runner). It watches
Google Drive folders, copies each submitted job to local scratch, runs it with
``cochem-cli run`` when the workstation owner is not using the machine, and
writes ``jobs/<label>/status.json`` plus a results zip back into the same
folder. Nothing here hard-codes a folder: each user assigns one in BASE.

Two transports reach the assigned folder:

* a local path synced by Google Drive for desktop (instructor machines,
  personal computers), and
* a Google Drive folder link, used through the Drive API from Codespaces or
  GitHub Actions with credentials provided as a secret
  (``COCHEM_WORKSTATION_DRIVE_CREDENTIALS``: service-account JSON; the folder
  must be in a shared drive the account can write to, or
  ``COCHEM_WORKSTATION_DRIVE_TOKEN``: an OAuth access token). Credentials are
  never written into BASE settings, requests or results.

A workstation result is accepted only if its summary binds it to the exact
submitted ``calculation.json`` and every published BASE artifact matches its
recorded SHA-256. A COMPLETED workstation job is not scientific acceptance by
itself: BASE's own ``EXECUTION_VERIFIED`` execution record is required.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Protocol

from .student_request import canonical_json, safe_relative_path, strict_json

SCHEMA = "cochem.student-workstation/1"
SETTINGS_SCHEMA = "cochem.workstation-queue/1"
JOB_SCHEMA = "cochem.workstation-job/1"
STATUS_SCHEMA = "cochem.workstation-job-status/1"
SUMMARY_SCHEMA = "cochem.workstation-job-summary/1"
HEALTH_SCHEMA = "cochem.workstation-health/1"
FOLDER_SCHEMA = "cochem.workstation-folder/1"
FOLDER_MARKER = "cochem_workstation_folder.json"
ENGINE = "cochem_base"
FOLDER_MIME = "application/vnd.google-apps.folder"
DRIVE_LINK = re.compile(r"^(?:https://drive\.google\.com/(?:drive/(?:u/\d+/)?folders/|open\?id=)|drive:)"
                        r"([A-Za-z0-9_-]{10,200})(?:[/?#].*)?$")
STUDENT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
TERMINAL = {"COMPLETED", "FAILED", "CANCELLED"}
MAX_RESULT_BYTES = 4 * 1024 * 1024 * 1024
MAX_RESULT_FILES = 20000
MAX_HOURS = 168


class WorkstationQueueError(RuntimeError):
    """The workstation route is not configured, reachable or trustworthy."""


def _hash_bytes(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write(path: Path, data: dict) -> None:
    from cochem.core.context import AtomicWrite
    with AtomicWrite(path) as staged:
        staged.write_bytes(canonical_json(data))
        staged.chmod(0o600)


# ---------------------------------------------------------------------------
# Settings: the folder each user assigns
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WorkstationSettings:
    folder: str
    student_id: str
    cores: int | str = "auto"
    memory_gb: float | None = None
    max_hours: int = 48

    @property
    def drive_folder_id(self) -> str | None:
        match = DRIVE_LINK.match(self.folder.strip())
        return match[1] if match else None

    @property
    def transport(self) -> str:
        return "drive_api" if self.drive_folder_id else "local"

    def to_json(self) -> dict:
        return {"schema": SETTINGS_SCHEMA, **asdict(self)}


def validate_settings(value: dict) -> WorkstationSettings:
    if not isinstance(value, dict):
        raise ValueError("Workstation settings must be an object")
    value = dict(value)
    value.pop("schema", None)
    allowed = {"folder", "student_id", "cores", "memory_gb", "max_hours"}
    if set(value) - allowed or not {"folder", "student_id"} <= set(value):
        raise ValueError("Workstation settings need exactly a folder, a student ID and optional resources")
    folder, student = value["folder"], value["student_id"]
    if not isinstance(folder, str) or not folder.strip() or len(folder) > 1024 or any(ord(c) < 32 for c in folder):
        raise ValueError("Choose the Google Drive folder (a synced folder path or a drive.google.com folder link)")
    if not isinstance(student, str) or not STUDENT_ID.fullmatch(student):
        raise ValueError("Student ID: use 1-64 letters, digits, '.', '_' or '-'")
    cores = value.get("cores", "auto")
    if cores != "auto" and (type(cores) is not int or not 1 <= cores <= 256):
        raise ValueError("Cores must be 'auto' or a whole number from 1 to 256")
    memory = value.get("memory_gb")
    if memory is not None and (type(memory) not in (int, float) or not 0.25 <= memory <= 2048):
        raise ValueError("Memory must be between 0.25 and 2048 GB, or left empty")
    hours = value.get("max_hours", 48)
    if type(hours) is not int or not 1 <= hours <= MAX_HOURS:
        raise ValueError(f"Maximum hours must be a whole number from 1 to {MAX_HOURS}")
    folder = folder.strip()
    if not DRIVE_LINK.match(folder) and not Path(folder).expanduser().is_absolute():
        raise ValueError("Give the full path of the synced Google Drive folder, or its drive.google.com link")
    return WorkstationSettings(folder=folder, student_id=student, cores=cores,
                               memory_gb=float(memory) if memory is not None else None, max_hours=hours)


def settings_path(artifact_dir: Path | str | None = None) -> Path:
    from cochem_base.config_loader import get_artifact_dir
    return get_artifact_dir(artifact_dir) / "StudentSetup" / "workstation-queue.json"


def load_settings(artifact_dir: Path | str | None = None) -> WorkstationSettings | None:
    """Saved settings, overridden by ``COCHEM_WORKSTATION_FOLDER``/``COCHEM_WORKSTATION_STUDENT``."""
    saved: dict = {}
    path = settings_path(artifact_dir)
    if path.exists():
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
            raise WorkstationQueueError("Saved workstation settings are not an ordinary private settings file")
        saved = strict_json(path.read_bytes())
        if saved.get("schema") != SETTINGS_SCHEMA:
            raise WorkstationQueueError("Saved workstation settings use an unknown format")
    folder = os.environ.get("COCHEM_WORKSTATION_FOLDER") or saved.get("folder")
    student = os.environ.get("COCHEM_WORKSTATION_STUDENT") or saved.get("student_id")
    if not folder or not student:
        return None
    return validate_settings({**saved, "folder": folder, "student_id": student})


def save_settings(settings: WorkstationSettings, artifact_dir: Path | str | None = None) -> Path:
    path = settings_path(artifact_dir)
    _write(path, settings.to_json())
    return path


# ---------------------------------------------------------------------------
# Transports
# ---------------------------------------------------------------------------
class Transport(Protocol):
    description: str

    def ensure(self, student_id: str) -> None: ...
    def submit(self, job_name: str, files: dict[str, bytes]) -> None: ...
    def pending(self, job_name: str) -> bool: ...
    def status(self, job_name: str, client_job_id: str) -> dict | None: ...
    def download_result(self, status: dict, destination: Path) -> None: ...
    def cancel(self, job_name: str, status: dict | None) -> None: ...
    def health(self) -> list[dict]: ...


def _job_manifest(job_name: str, files: dict[str, bytes], *, student_id: str, client_job_id: str,
                  resources: dict) -> bytes:
    manifest = {"schema": JOB_SCHEMA, "engine": ENGINE, "name": job_name, "input": "calculation.json",
                "resources": resources, "job_id": client_job_id, "student_id": student_id,
                "files": {name: _hash_bytes(contents) for name, contents in sorted(files.items())}}
    return json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")


def _health_document(contents: bytes) -> dict | None:
    try:
        doc = strict_json(contents)
    except ValueError:
        return None
    if doc.get("schema") != HEALTH_SCHEMA:
        return None
    age = time.time() - float(doc.get("updated_epoch", 0))
    doc["stale"] = age > float(doc.get("stale_after_seconds", 600))
    return doc


def _status_document(contents: bytes, client_job_id: str) -> dict | None:
    try:
        doc = strict_json(contents)
    except ValueError:
        return None
    if doc.get("schema") != STATUS_SCHEMA or doc.get("client_job_id") != client_job_id:
        return None
    return doc


class LocalFolderTransport:
    """A folder on this computer that Google Drive for desktop keeps in sync."""

    def __init__(self, folder: Path | str) -> None:
        self.folder = Path(folder).expanduser()
        self.description = str(self.folder)

    def _require(self) -> None:
        if not (self.folder / "inbox").is_dir():
            raise WorkstationQueueError(f"{self.folder} is not an assigned workstation folder (missing inbox/); "
                                        "is Google Drive for desktop running?")

    def ensure(self, student_id: str) -> None:
        if not self.folder.parent.is_dir():
            raise WorkstationQueueError(f"{self.folder.parent} does not exist; is Google Drive for desktop running?")
        (self.folder / "inbox").mkdir(parents=True, exist_ok=True)
        (self.folder / "jobs").mkdir(parents=True, exist_ok=True)
        marker = self.folder / FOLDER_MARKER
        current = None
        if marker.is_file():
            try:
                current = strict_json(marker.read_bytes())
            except ValueError:
                current = None
        if not current or current.get("schema") != FOLDER_SCHEMA or current.get("student_id") != student_id:
            marker.write_text(json.dumps({"schema": FOLDER_SCHEMA, "student_id": student_id,
                                          "created_by": "CoChem-BASE"}, indent=2) + "\n", encoding="utf-8")

    def submit(self, job_name: str, files: dict[str, bytes]) -> None:
        self._require()
        inbox = self.folder / "inbox"
        staging = inbox / f".cochem-upload-{uuid.uuid4().hex[:12]}"
        staging.mkdir()
        try:
            for name, contents in files.items():
                target = staging / safe_relative_path(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(contents)
            os.replace(staging, inbox / job_name)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def pending(self, job_name: str) -> bool:
        return (self.folder / "inbox" / job_name).is_dir()

    def _job_folder(self, job_name: str, client_job_id: str) -> tuple[Path, dict] | None:
        for path in sorted((self.folder / "jobs").glob(job_name + "__*/status.json")):
            try:
                doc = _status_document(path.read_bytes(), client_job_id)
            except OSError:
                continue
            if doc is not None:
                return path.parent, doc
        return None

    def status(self, job_name: str, client_job_id: str) -> dict | None:
        found = self._job_folder(job_name, client_job_id)
        return found[1] if found else None

    def download_result(self, status: dict, destination: Path) -> None:
        name = status.get("result_file")
        if not isinstance(name, str) or "/" in name or "\\" in name:
            raise WorkstationQueueError("The workstation has not published a results archive")
        source = self.folder / "jobs" / str(status["label"]) / name
        if source.is_symlink() or not source.is_file():
            raise WorkstationQueueError("The results archive has not finished syncing to this computer yet")
        shutil.copyfile(source, destination)

    def cancel(self, job_name: str, status: dict | None) -> None:
        if status is None and self.pending(job_name):
            shutil.rmtree(self.folder / "inbox" / job_name)
            return
        if status is not None:
            (self.folder / "jobs" / str(status["label"]) / "CANCEL").write_text("cancel requested\n", encoding="utf-8")

    def health(self) -> list[dict]:
        documents = {}
        for status_dir in (self.folder / "_status", self.folder.parent / "_status"):
            for path in sorted(status_dir.glob("workstation_health.*.json")):
                try:
                    doc = _health_document(path.read_bytes())
                except OSError:
                    continue
                if doc is not None:
                    documents[str(doc.get("node_id"))] = doc
        return list(documents.values())


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


class DriveApiTransport:
    """A Google Drive folder reached through the Drive v3 REST API (Codespaces, Actions)."""

    API = "https://www.googleapis.com/drive/v3"
    UPLOAD = "https://www.googleapis.com/upload/drive/v3"
    TOKEN = "https://oauth2.googleapis.com/token"
    SCOPE = "https://www.googleapis.com/auth/drive"

    def __init__(self, folder_id: str, *, credentials: dict | None = None, access_token: str | None = None,
                 api_url: str | None = None, upload_url: str | None = None, allow_loopback: bool = False,
                 timeout: float = 60.0) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,200}", folder_id or ""):
            raise WorkstationQueueError("The Google Drive folder link does not contain a valid folder ID")
        self.folder_id = folder_id
        self.description = f"Google Drive folder {folder_id}"
        self.api = (api_url or self.API).rstrip("/")
        self.upload = (upload_url or self.UPLOAD).rstrip("/")
        self.allow_loopback = allow_loopback
        self.timeout = timeout
        self._credentials = credentials
        self._token = access_token
        self._token_expiry = float("inf") if access_token else 0.0
        self._ids: dict[str, str] = {}
        for url in (self.api, self.upload, (credentials or {}).get("token_uri", self.TOKEN)):
            self._check_url(url)

    @classmethod
    def from_environment(cls, folder_id: str, **kwargs: Any) -> DriveApiTransport:
        token = os.environ.get("COCHEM_WORKSTATION_DRIVE_TOKEN")
        if token:
            return cls(folder_id, access_token=token.strip(), **kwargs)
        text = os.environ.get("COCHEM_WORKSTATION_DRIVE_CREDENTIALS")
        path = os.environ.get("COCHEM_WORKSTATION_DRIVE_CREDENTIALS_FILE") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if not text and path:
            try:
                text = Path(path).read_text(encoding="utf-8")
            except OSError as error:
                raise WorkstationQueueError(f"Cannot read the Drive credentials file: {error}") from None
        if not text:
            raise WorkstationQueueError(
                "Reaching a Google Drive folder link needs Drive access: ask your instructor to add the "
                "COCHEM_WORKSTATION_DRIVE_CREDENTIALS secret to your Codespace, or use a folder synced by "
                "Google Drive for desktop on this computer")
        try:
            credentials = json.loads(text)
        except ValueError:
            raise WorkstationQueueError("COCHEM_WORKSTATION_DRIVE_CREDENTIALS is not service-account JSON") from None
        if not isinstance(credentials, dict) or credentials.get("type") != "service_account" \
                or not {"client_email", "private_key"} <= set(credentials):
            raise WorkstationQueueError("Drive credentials must be a Google service-account key (JSON)")
        return cls(folder_id, credentials=credentials, **kwargs)

    def _check_url(self, url: str) -> None:
        parsed = urllib.parse.urlparse(url)
        loopback = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        if parsed.scheme == "https" and not loopback:
            if not (parsed.hostname or "").endswith(".googleapis.com"):
                raise WorkstationQueueError("Drive access is limited to Google's API endpoints")
            return
        if not (self.allow_loopback and loopback and parsed.scheme in {"http", "https"}):
            raise WorkstationQueueError("Drive access requires HTTPS to Google's API endpoints")

    # -- authentication ------------------------------------------------
    def _access_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        if not self._credentials:
            raise WorkstationQueueError("The Drive access token expired; refresh COCHEM_WORKSTATION_DRIVE_TOKEN")
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        try:
            key = serialization.load_pem_private_key(self._credentials["private_key"].encode(), password=None)
        except (ValueError, TypeError):
            raise WorkstationQueueError("The Drive service-account key cannot be loaded") from None
        if not isinstance(key, rsa.RSAPrivateKey):
            raise WorkstationQueueError("The Drive service-account key must be an RSA key")
        token_uri = self._credentials.get("token_uri", self.TOKEN)
        now = int(time.time())
        claims = {"iss": self._credentials["client_email"], "scope": self.SCOPE, "aud": token_uri,
                  "iat": now, "exp": now + 3600}
        message = (_b64url(b'{"alg":"RS256","typ":"JWT"}') + "." +
                   _b64url(json.dumps(claims, separators=(",", ":")).encode())).encode("ascii")
        assertion = message.decode("ascii") + "." + _b64url(key.sign(message, padding.PKCS1v15(), hashes.SHA256()))
        body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                                       "assertion": assertion}).encode()
        request = urllib.request.Request(token_uri, data=body, method="POST",
                                         headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                value = json.loads(response.read())
        except (urllib.error.URLError, ValueError, OSError) as error:
            raise WorkstationQueueError(f"Google rejected the Drive service-account sign-in: {error}") from None
        if not isinstance(value.get("access_token"), str):
            raise WorkstationQueueError("Google returned no Drive access token")
        self._token = value["access_token"]
        self._token_expiry = time.time() + float(value.get("expires_in", 3600))
        return self._token

    def _call(self, method: str, url: str, *, params: dict | None = None, body: bytes | None = None,
              content_type: str | None = None, raw: bool = False, sink: Path | None = None) -> Any:
        query = {"supportsAllDrives": "true", **(params or {})}
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(query)
        for attempt in range(4):
            headers = {"Authorization": "Bearer " + self._access_token()}
            if content_type:
                headers["Content-Type"] = content_type
            request = urllib.request.Request(url, data=body, method=method, headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    if sink is not None:
                        with sink.open("wb") as stream:
                            shutil.copyfileobj(response, stream, 1024 * 1024)
                        return None
                    contents = response.read()
                    return contents if raw else (json.loads(contents) if contents else {})
            except urllib.error.HTTPError as error:
                if error.code in {429, 500, 502, 503, 504} and attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                if error.code == 404:
                    raise FileNotFoundError(url) from None
                detail = error.read(2000).decode("utf-8", "replace")
                if "storageQuotaExceeded" in detail or "do not have storage quota" in detail:
                    raise WorkstationQueueError(
                        "The Drive service account cannot own files in a personal My Drive folder; place the "
                        "workstation folder in a shared drive the account can edit") from None
                raise WorkstationQueueError(f"Google Drive refused the request ({error.code}): {detail[:300]}") from None
            except (urllib.error.URLError, OSError) as error:
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                raise WorkstationQueueError(f"Google Drive is unreachable: {error}") from None
        raise WorkstationQueueError("Google Drive kept refusing the request")  # pragma: no cover

    def _list(self, query: str) -> list[dict]:
        found, token = [], None
        while True:
            params = {"q": query + " and trashed = false", "includeItemsFromAllDrives": "true", "pageSize": "1000",
                      "fields": "nextPageToken,files(id,name,mimeType,size)"}
            if token:
                params["pageToken"] = token
            page = self._call("GET", self.api + "/files", params=params)
            found += page.get("files", [])
            token = page.get("nextPageToken")
            if not token:
                return found

    def _child(self, parent: str, name: str, *, folder: bool | None = None) -> dict | None:
        query = f"'{_quote(parent)}' in parents and name = '{_quote(name)}'"
        if folder is not None:
            query += f" and mimeType {'=' if folder else '!='} '{FOLDER_MIME}'"
        matches = self._list(query)
        return matches[0] if matches else None

    def _create_folder(self, parent: str, name: str) -> str:
        body = json.dumps({"name": name, "mimeType": FOLDER_MIME, "parents": [parent]}).encode()
        return self._call("POST", self.api + "/files", params={"fields": "id"}, body=body,
                          content_type="application/json")["id"]

    def _upload(self, parent: str, name: str, contents: bytes) -> str:
        boundary = "cochem-" + uuid.uuid4().hex
        metadata = json.dumps({"name": name, "parents": [parent]}).encode()
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode() + metadata +
                f"\r\n--{boundary}\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + contents +
                f"\r\n--{boundary}--\r\n".encode())
        return self._call("POST", self.upload + "/files", params={"uploadType": "multipart", "fields": "id"},
                          body=body, content_type=f"multipart/related; boundary={boundary}")["id"]

    def _folder(self, name: str, *, create: bool = False) -> str:
        if name not in self._ids:
            found = self._child(self.folder_id, name, folder=True)
            if found is None:
                if not create:
                    raise WorkstationQueueError(f"The Drive folder has no {name}/ folder; assign it again in BASE")
                self._ids[name] = self._create_folder(self.folder_id, name)
            else:
                self._ids[name] = found["id"]
        return self._ids[name]

    # -- transport interface -------------------------------------------
    def ensure(self, student_id: str) -> None:
        try:
            meta = self._call("GET", self.api + "/files/" + self.folder_id, params={"fields": "id,name,mimeType"})
        except FileNotFoundError:
            raise WorkstationQueueError("The Drive folder does not exist or is not shared with BASE's Drive account") from None
        if meta.get("mimeType") != FOLDER_MIME:
            raise WorkstationQueueError("The Drive link does not point to a folder")
        self._folder("inbox", create=True)
        self._folder("jobs", create=True)
        marker = self._child(self.folder_id, FOLDER_MARKER, folder=False)
        if marker is not None:
            current = strict_json(self._call("GET", self.api + "/files/" + marker["id"], params={"alt": "media"}, raw=True))
            if current.get("student_id") == student_id:
                return
            body = json.dumps({"schema": FOLDER_SCHEMA, "student_id": student_id, "created_by": "CoChem-BASE"}).encode()
            self._call("PATCH", self.upload + "/files/" + marker["id"], params={"uploadType": "media"}, body=body,
                       content_type="application/json")
            return
        self._upload(self.folder_id, FOLDER_MARKER, json.dumps({"schema": FOLDER_SCHEMA, "student_id": student_id,
                                                                "created_by": "CoChem-BASE"}, indent=2).encode())

    def submit(self, job_name: str, files: dict[str, bytes]) -> None:
        inbox = self._folder("inbox")
        staging = self._create_folder(inbox, f".cochem-upload-{uuid.uuid4().hex[:12]}")
        folders = {(): staging}
        for name, contents in files.items():
            parts = safe_relative_path(name).parts
            for depth in range(1, len(parts)):
                if parts[:depth] not in folders:
                    folders[parts[:depth]] = self._create_folder(folders[parts[:depth - 1]], parts[depth - 1])
            self._upload(folders[parts[:-1]], parts[-1], contents)
        # Renaming the finished upload is what makes it visible to the workstation.
        self._call("PATCH", self.api + "/files/" + staging, params={"fields": "id"},
                   body=json.dumps({"name": job_name}).encode(), content_type="application/json")

    def pending(self, job_name: str) -> bool:
        return self._child(self._folder("inbox"), job_name, folder=True) is not None

    def _job_folder(self, job_name: str, client_job_id: str) -> tuple[str, dict] | None:
        query = f"'{_quote(self._folder('jobs'))}' in parents and name contains '{_quote(job_name)}__'"
        for folder in self._list(query + f" and mimeType = '{FOLDER_MIME}'"):
            if not folder["name"].startswith(job_name + "__"):
                continue
            status = self._child(folder["id"], "status.json", folder=False)
            if status is None:
                continue
            doc = _status_document(self._call("GET", self.api + "/files/" + status["id"],
                                              params={"alt": "media"}, raw=True), client_job_id)
            if doc is not None:
                return folder["id"], doc
        return None

    def status(self, job_name: str, client_job_id: str) -> dict | None:
        found = self._job_folder(job_name, client_job_id)
        if found is None:
            return None
        self._ids["job:" + job_name] = found[0]
        return found[1]

    def download_result(self, status: dict, destination: Path) -> None:
        job_name = str(status["label"]).rsplit("__", 1)[0]
        folder = self._ids.get("job:" + job_name)
        if folder is None:
            found = self._job_folder(job_name, str(status.get("client_job_id")))
            if found is None:
                raise WorkstationQueueError("The workstation job folder is no longer in Drive")
            folder = found[0]
        archive = self._child(folder, str(status.get("result_file")), folder=False)
        if archive is None:
            raise WorkstationQueueError("The results archive is not in Drive yet")
        if int(archive.get("size", 0)) > MAX_RESULT_BYTES:
            raise WorkstationQueueError("The results archive exceeds BASE's retrieval limit")
        self._call("GET", self.api + "/files/" + archive["id"], params={"alt": "media"}, sink=destination)

    def cancel(self, job_name: str, status: dict | None) -> None:
        if status is None:
            pending = self._child(self._folder("inbox"), job_name, folder=True)
            if pending is not None:
                self._call("DELETE", self.api + "/files/" + pending["id"], raw=True)
            return
        found = self._job_folder(job_name, str(status.get("client_job_id")))
        if found is not None:
            self._upload(found[0], "CANCEL", b"cancel requested\n")

    def health(self) -> list[dict]:
        documents = {}
        parents = []
        try:
            meta = self._call("GET", self.api + "/files/" + self.folder_id, params={"fields": "parents"})
            parents = list(meta.get("parents") or [])
        except (FileNotFoundError, WorkstationQueueError):
            pass
        for parent in [self.folder_id, *parents[:1]]:
            try:
                status_dir = self._child(parent, "_status", folder=True)
            except WorkstationQueueError:
                continue
            if status_dir is None:
                continue
            for item in self._list(f"'{_quote(status_dir['id'])}' in parents and name contains 'workstation_health.'"):
                doc = _health_document(self._call("GET", self.api + "/files/" + item["id"],
                                                  params={"alt": "media"}, raw=True))
                if doc is not None:
                    documents[str(doc.get("node_id"))] = doc
        return list(documents.values())


def open_transport(settings: WorkstationSettings, **drive_options: Any) -> Transport:
    folder_id = settings.drive_folder_id
    if folder_id:
        return DriveApiTransport.from_environment(folder_id, **drive_options)
    return LocalFolderTransport(settings.folder)


def assign_folder(folder: str, student_id: str, *, artifact_dir: Path | str | None = None, cores: int | str = "auto",
                  memory_gb: float | None = None, max_hours: int = 48, transport: Transport | None = None) -> dict:
    """Validate, prepare (inbox/, jobs/, identity marker) and save the user's chosen folder."""
    settings = validate_settings({"folder": folder, "student_id": student_id, "cores": cores,
                                  "memory_gb": memory_gb, "max_hours": max_hours})
    transport = transport or open_transport(settings)
    transport.ensure(settings.student_id)
    path = save_settings(settings, artifact_dir)
    return {"settings": settings.to_json(), "settings_path": str(path), "transport": settings.transport,
            "workstations": summarize_health(transport.health())}


def summarize_health(documents: list[dict]) -> list[dict]:
    summary = []
    for doc in documents:
        capacity = doc.get("capacity", {})
        summary.append({"node_id": doc.get("node_id"), "mode": doc.get("mode"), "stale": bool(doc.get("stale")),
                        "accepting_jobs": bool(doc.get("accepting_jobs")) and not doc.get("stale"),
                        "cores_available": capacity.get("cores_available_for_jobs"),
                        "gpu_available": capacity.get("gpu_available_for_jobs"),
                        "queued": sum((doc.get("queue") or {}).values()),
                        "engines": doc.get("engines", []), "reasons": doc.get("reasons", [])})
    return summary


# ---------------------------------------------------------------------------
# When the hosted classroom worker is not enough
# ---------------------------------------------------------------------------
def actions_limit_reasons(calculation: dict, *, cores: int = 2, maxcore_mb: int = 1024) -> list[str]:
    """Why a calculation cannot run on the classroom GitHub Actions worker (empty if it can)."""
    from . import actions_jobs
    reasons = []
    try:
        actions_jobs.validate_resources(cores, maxcore_mb)
    except ValueError as error:
        reasons.append(str(error))
    if not isinstance(calculation, dict):
        return reasons
    try:
        from cochem_base.calc.calculation_service import parse_run_geometry
        atoms = len(parse_run_geometry(calculation.get("geometry", ""))[0])
        if atoms > actions_jobs.MAX_ATOMS:
            reasons.append(f"{atoms} atoms exceeds the classroom limit of {actions_jobs.MAX_ATOMS}")
    except Exception:  # geometry problems are reported by full validation
        pass
    timeout = calculation.get("timeout_seconds", 3600.0)
    if isinstance(timeout, (int, float)) and timeout > actions_jobs.MAX_TIMEOUT_SECONDS:
        reasons.append(f"a {timeout / 60:.0f}-minute calculation exceeds the classroom limit of "
                       f"{actions_jobs.MAX_TIMEOUT_SECONDS // 60} minutes")
    if calculation.get("engine") not in {"orca", "cfour"}:
        reasons.append(f"the classroom worker runs ORCA or CFOUR, not {calculation.get('engine')!r}")
    return reasons


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
def _safe_extract(archive: Path, destination: Path) -> list[str]:
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if len(members) > MAX_RESULT_FILES or sum(m.file_size for m in members) > MAX_RESULT_BYTES:
            raise WorkstationQueueError("The results archive is larger than BASE retrieves")
        names = []
        for member in members:
            if member.is_dir():
                continue
            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise WorkstationQueueError("The results archive contains a link")
            path = PurePosixPath(member.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or not path.parts or ":" in path.parts[0]:
                raise WorkstationQueueError("The results archive contains an unsafe path")
            target = destination.joinpath(*path.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(member) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink, 1024 * 1024)
            names.append(path.as_posix())
    return sorted(names)


TRANSIENT = ("*.tmp", "*.tmp.*", "*.proc*", "*.lock")


def _verify_published_checksums(extracted: Path, summary: dict) -> list[str]:
    """Check every BASE ``<file>.sha256`` sidecar; return files the workstation deliberately omitted."""
    import fnmatch
    output = extracted / "base_output"
    if not output.is_dir():
        return []
    reported = " ".join(summary.get("files_not_included") or [])
    omitted = []
    for sidecar in sorted(output.rglob("*.sha256")):
        target = sidecar.with_name(sidecar.name[:-len(".sha256")])
        relative = target.relative_to(extracted).as_posix()
        fields = sidecar.read_text(encoding="utf-8").split()
        if not fields or not re.fullmatch(r"[0-9a-f]{64}", fields[0]):
            raise WorkstationQueueError("A returned BASE checksum record is malformed: " + relative)
        if not target.exists():
            if any(fnmatch.fnmatch(target.name, pattern) for pattern in TRANSIENT) or relative in reported:
                omitted.append(relative)
                continue
            raise WorkstationQueueError("A returned BASE artifact is missing: " + relative)
        if target.is_symlink() or not target.is_file() or _hash(target) != fields[0]:
            raise WorkstationQueueError("A returned BASE artifact differs from its recorded checksum: " + relative)
    return omitted


class StudentWorkstationClient:
    """Submit, follow and retrieve BASE calculations run by the lab workstation."""

    def __init__(self, *, artifact_dir: Path | str | None = None, settings: WorkstationSettings | None = None,
                 transport: Transport | None = None) -> None:
        from cochem_base.config_loader import get_artifact_dir
        self.artifact_dir = get_artifact_dir(artifact_dir)
        self.jobs = self.artifact_dir / "StudentWorkstation"
        self.settings = settings if settings is not None else load_settings(self.artifact_dir)
        self._transport = transport

    @property
    def transport(self) -> Transport:
        if self.settings is None:
            raise WorkstationQueueError("Assign your workstation Drive folder first (Workstation settings)")
        if self._transport is None:
            self._transport = open_transport(self.settings)
        return self._transport

    def preflight(self) -> dict:
        try:
            transport = self.transport
            workstations = summarize_health(transport.health())
        except (WorkstationQueueError, OSError, ValueError) as error:
            return {"ready": False, "reason": str(error), "workstations": []}
        live = [w for w in workstations if w["accepting_jobs"]]
        if not workstations:
            reason = ("Jobs are queued in your folder; no workstation has reported for it yet, so they start "
                      "when the workstation owner adds your folder")
        elif not live:
            reason = "Jobs are queued in your folder; the workstation is currently offline or not accepting jobs"
        else:
            best = max(live, key=lambda w: w.get("cores_available") or 0)
            reason = (f"Workstation {best['node_id']} is accepting jobs ({best['mode']}, "
                      f"{best.get('cores_available') or 0} cores free now)")
        return {"ready": True, "reason": reason, "transport": self.settings.transport, "folder": self.settings.folder,
                "workstations": workstations}

    def submit(self, calculation: dict, *, cores: int | str | None = None, memory_gb: float | None = None) -> dict:
        settings = self.settings
        if settings is None:
            raise WorkstationQueueError("Assign your workstation Drive folder first (Workstation settings)")
        cores = settings.cores if cores is None else cores
        memory_gb = settings.memory_gb if memory_gb is None else memory_gb
        if cores != "auto" and (type(cores) is not int or not 1 <= cores <= 256):
            raise ValueError("Cores must be 'auto' or a whole number from 1 to 256")
        from .student_hpc import validate_portable_calculation
        memory_mb = int((memory_gb or 64) * 1024)
        calculation = validate_portable_calculation(
            calculation, resources={"walltime": f"{settings.max_hours}:00:00",
                                    "cores": cores if isinstance(cores, int) else 256, "memory_mb": memory_mb})
        if calculation.get("engine") == "qe":
            raise ValueError("Periodic QE calculations need their PAW inputs bundle; use the HPC or local route")
        request_id = str(uuid.uuid4())
        job_name = "base-" + request_id[:8]
        client_job_id = "cochem-base:" + request_id
        payload = json.dumps(calculation, indent=2, sort_keys=True).encode("utf-8")
        resources: dict[str, Any] = {"cores": cores, "max_hours": settings.max_hours}
        if memory_gb is not None:
            resources["memory_gb"] = memory_gb
        files = {"calculation.json": payload}
        files["job.json"] = _job_manifest(job_name, files, student_id=settings.student_id,
                                          client_job_id=client_job_id, resources=resources)
        package = self.jobs / request_id
        package.mkdir(parents=True, exist_ok=False)
        request = {"schema_version": SCHEMA, "request_id": request_id, "client_job_id": client_job_id,
                   "job_name": job_name, "calculation": calculation, "resources": resources,
                   "calculation_sha256": _hash_bytes(payload), "folder": settings.folder,
                   "transport": settings.transport, "student_id": settings.student_id,
                   "created_at": datetime.now(timezone.utc).isoformat()}
        _write(package / "request.json", request)
        self.transport.submit(job_name, files)
        submission = {"schema_version": SCHEMA, "request_id": request_id, "client_job_id": client_job_id,
                      "job_name": job_name, "folder": settings.folder, "transport": settings.transport,
                      "request_sha256": _hash(package / "request.json"),
                      "submitted_at": datetime.now(timezone.utc).isoformat()}
        _write(package / "submission.json", submission)
        return submission

    def _saved(self, submission: dict) -> tuple[Path, dict, dict]:
        if not isinstance(submission, dict) or not isinstance(submission.get("request_id"), str):
            raise WorkstationQueueError("Select an original saved workstation submission")
        try:
            identity = str(uuid.UUID(submission["request_id"]))
        except ValueError:
            raise WorkstationQueueError("Invalid workstation request identifier") from None
        package = self.jobs / identity
        if package.is_symlink() or not package.is_dir():
            raise WorkstationQueueError("The workstation submission lost its original package directory")
        saved = strict_json((package / "submission.json").read_bytes())
        if any(submission.get(key) != value for key, value in saved.items()) or \
                set(submission) - set(saved) - {"status", "conclusion", "detail"}:
            raise WorkstationQueueError("Workstation job differs from the original saved submission")
        if _hash(package / "request.json") != saved["request_sha256"]:
            raise WorkstationQueueError("The original workstation request changed")
        return package, saved, strict_json((package / "request.json").read_bytes())

    def history(self) -> list[dict]:
        if not self.jobs.is_dir():
            return []
        records = []
        for path in sorted(self.jobs.glob("*/submission.json")):
            saved = strict_json(path.read_bytes())
            self._saved(saved)
            records.append(saved)
        return records

    list_submissions = history

    def status(self, submission: dict) -> dict:
        package, saved, _request = self._saved(submission)
        retained = package / "results" / "workstation-result.json"
        if retained.is_file():
            report = strict_json(retained.read_bytes())
            return {"status": "completed", "conclusion": "success" if report["status"] == "completed" else "failure",
                    "workstation_state": report.get("workstation_state"), "detail": report.get("message", ""),
                    "request_id": saved["request_id"], "label": report.get("label"), "progress": {}, "output_tail": []}
        transport = self.transport
        remote = transport.status(saved["job_name"], saved["client_job_id"])
        if remote is None:
            waiting = transport.pending(saved["job_name"])
            return {"status": "queued" if waiting else "unknown", "conclusion": None, "workstation_state": None,
                    "detail": ("Waiting for the workstation to pick the job up from your folder" if waiting
                               else "The job is neither in your inbox nor in jobs/ yet (Drive may still be syncing)"),
                    "request_id": saved["request_id"], "label": None, "progress": {}, "output_tail": []}
        state = remote.get("state")
        status, conclusion = {"QUEUED": ("queued", None), "PAUSED": ("queued", None),
                              "RUNNING": ("running", None), "SUSPENDED": ("running", None)}.get(state, ("unknown", None))
        if state in TERMINAL:
            # Terminal only once the results archive (if any) has been published.
            if remote.get("result_file") or remote.get("attempts", 0) == 0:
                status = "completed"
                conclusion = {"COMPLETED": "success", "FAILED": "failure", "CANCELLED": "cancelled"}[state]
            else:
                status = "running"
        detail = remote.get("message") or remote.get("explanation") or ""
        if state in {"SUSPENDED", "PAUSED"}:
            detail = "Paused while the workstation owner uses the machine; it continues automatically. " + detail
        return {"status": status, "conclusion": conclusion, "workstation_state": state, "detail": detail.strip(),
                "request_id": saved["request_id"], "label": remote.get("label"),
                "progress": remote.get("progress") or {}, "output_tail": remote.get("output_tail") or [],
                "resources": remote.get("resources") or {}, "repairs": remote.get("repairs") or [],
                "queue_position": remote.get("queue_position")}

    def cancel(self, submission: dict) -> None:
        _package, saved, _request = self._saved(submission)
        self.transport.cancel(saved["job_name"], self.transport.status(saved["job_name"], saved["client_job_id"]))

    def retrieve_results(self, submission: dict) -> dict:
        """Download, verify and retain the workstation's results for this exact submission."""
        package, saved, request = self._saved(submission)
        root = package / "results"
        retained = root / "workstation-result.json"
        if retained.is_file():
            report = strict_json(retained.read_bytes())
            return {"path": str(root), "report": report, "files": report["files"]}
        remote = self.transport.status(saved["job_name"], saved["client_job_id"])
        if remote is None or remote.get("state") not in TERMINAL:
            raise WorkstationQueueError("The workstation has not finished this job yet")
        report: dict[str, Any] = {"schema_version": SCHEMA, "request_id": saved["request_id"],
                                  "client_job_id": saved["client_job_id"], "label": remote.get("label"),
                                  "workstation": remote.get("workstation"), "workstation_state": remote["state"],
                                  "message": remote.get("message", ""), "resources": remote.get("resources"),
                                  "repairs": remote.get("repairs") or [], "operation_performed": False,
                                  "status": "failed", "execution": None, "files": []}
        staging = Path(tempfile.mkdtemp(prefix=".results-", dir=package))
        try:
            if remote.get("result_file"):
                archive = staging / "results.zip"
                self.transport.download_result(remote, archive)
                expected = remote.get("result_sha256")
                if expected and _hash(archive) != expected:
                    raise WorkstationQueueError("The results archive is still syncing (checksum differs); try again shortly")
                extracted = staging / "results"
                files = _safe_extract(archive, extracted)
                summary = strict_json((extracted / "_runner" / "job_summary.json").read_bytes())
                if (summary.get("schema") != SUMMARY_SCHEMA or summary.get("client_job_id") != saved["client_job_id"]
                        or (summary.get("input_hashes") or {}).get("calculation.json") != request["calculation_sha256"]):
                    raise WorkstationQueueError("The returned results belong to a different calculation")
                omitted = _verify_published_checksums(extracted, summary)
                execution = None
                execution_path = extracted / "base_output" / "execution.json"
                if execution_path.is_file():
                    execution = strict_json(execution_path.read_bytes())
                report["omitted_files"] = omitted
                verified = bool(execution and execution.get("status") in {"EXECUTION_VERIFIED", "T9_FALLBACK_VERIFIED"})
                report.update(files=files, execution=execution, operation_performed=verified,
                              status="completed" if remote["state"] == "COMPLETED" and verified else "failed")
                if remote["state"] == "COMPLETED" and not verified:
                    report["message"] = ("The workstation finished, but BASE's verified execution record is "
                                         "missing; the result is not accepted")
                shutil.move(str(extracted), str(root))
            else:
                root.mkdir()
            _write(retained, report)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return {"path": str(root), "report": report, "files": report["files"]}
