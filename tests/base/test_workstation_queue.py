"""Workstation queue: user-assigned Drive folders, submission, status and verified retrieval.

The Drive API cases run against a real loopback HTTP server that implements
the subset of Google Drive v3 used by BASE and verifies the service-account
JWT signature. Workstation status/summary documents below are protocol
records of the job runner; no scientific result or execution record is
fabricated - completed science is accepted only with BASE's own verified
execution record, which these cases deliberately do not provide.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import threading
import time
import urllib.parse
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from cochem_base.interfaces.workstation_queue import (
    FOLDER_MARKER,
    DriveApiTransport,
    LocalFolderTransport,
    StudentWorkstationClient,
    WorkstationQueueError,
    WorkstationSettings,
    actions_limit_reasons,
    assign_folder,
    load_settings,
    validate_settings,
)

WATER = "O 0 0 0\nH 0.7586 0 0.5043\nH -0.7586 0 0.5043"
CALCULATION = {"geometry": WATER, "engine": "pyscf", "method": "HF", "basis_set": "sto-3g", "charge": 0,
               "multiplicity": 1, "is_opt": False, "is_freq": False}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _results_zip(*, client_job_id: str, calculation_sha256: str, extra: dict[str, bytes] | None = None,
                 summary: dict | None = None) -> bytes:
    """A runner results archive for a run that produced no BASE execution record."""
    document = {"schema": "cochem.workstation-job-summary/1", "client_job_id": client_job_id,
                "input_hashes": {"calculation.json": calculation_sha256}, "state": "FAILED"}
    document.update(summary or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as bundle:
        bundle.writestr("_runner/job_summary.json", json.dumps(document))
        bundle.writestr("cochem_base_run.log", "Calculation was not accepted: no registry\n")
        for name, contents in (extra or {}).items():
            bundle.writestr(name, contents)
    return stream.getvalue()


def _status(*, label: str, client_job_id: str, state: str, result: bytes | None = None, attempts: int = 1) -> dict:
    return {"schema": "cochem.workstation-job-status/1", "label": label, "client_job_id": client_job_id,
            "state": state, "message": "the workstation reported " + state.lower(), "attempts": attempts,
            "workstation": "lab-ws", "result_file": f"{label}_results.zip" if result is not None else None,
            "result_sha256": _sha(result) if result is not None else None, "progress": {}, "output_tail": []}


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------
def test_settings_validation_and_transport_kind(tmp_path):
    local = validate_settings({"folder": str(tmp_path / "Drive" / "CoChem"), "student_id": "alice"})
    assert local.transport == "local" and local.cores == "auto"
    remote = validate_settings({"folder": "https://drive.google.com/drive/u/0/folders/1AbCdEfGhIjKlMn?usp=sharing",
                                "student_id": "alice", "cores": 8, "memory_gb": 16})
    assert remote.transport == "drive_api" and remote.drive_folder_id == "1AbCdEfGhIjKlMn"
    for bad in ({"folder": "relative/path", "student_id": "a"}, {"folder": str(tmp_path), "student_id": "bad id"},
                {"folder": str(tmp_path), "student_id": "a", "cores": 0}, {"folder": str(tmp_path)},
                {"folder": str(tmp_path), "student_id": "a", "extra": 1}):
        with pytest.raises(ValueError):
            validate_settings(bad)


def test_assign_local_folder_persists_and_environment_overrides(tmp_path):
    artifacts = tmp_path / "artifacts"
    drive = tmp_path / "GoogleDrive"
    drive.mkdir()
    result = assign_folder(str(drive / "My CoChem jobs"), "alice", artifact_dir=artifacts, cores=4)
    folder = drive / "My CoChem jobs"
    assert (folder / "inbox").is_dir() and (folder / "jobs").is_dir()
    assert json.loads((folder / FOLDER_MARKER).read_text())["student_id"] == "alice"
    assert result["transport"] == "local" and result["workstations"] == []
    saved = load_settings(artifacts)
    assert saved.folder == str(folder) and saved.cores == 4
    previous = {key: os.environ.get(key) for key in ("COCHEM_WORKSTATION_FOLDER", "COCHEM_WORKSTATION_STUDENT")}
    os.environ.update(COCHEM_WORKSTATION_FOLDER=str(tmp_path / "other"), COCHEM_WORKSTATION_STUDENT="bob")
    try:
        overridden = load_settings(artifacts)
        assert overridden.folder == str(tmp_path / "other") and overridden.student_id == "bob" and overridden.cores == 4
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    with pytest.raises(WorkstationQueueError, match="Google Drive for desktop"):
        assign_folder(str(tmp_path / "not-mounted" / "x"), "alice", artifact_dir=artifacts)


def test_actions_limits_explain_when_to_use_the_workstation():
    small = dict(CALCULATION, engine="orca", method="B3LYP", basis_set="def2-SVP", timeout_seconds=600)
    assert actions_limit_reasons(small, cores=2, maxcore_mb=512) == []
    big = dict(small, geometry="\n".join(f"C {i * 1.5} 0 0" for i in range(60)), timeout_seconds=7200)
    reasons = actions_limit_reasons(big, cores=8, maxcore_mb=4000)
    assert any("1 or 2 CPU cores" in r for r in reasons)
    assert any("60 atoms" in r for r in reasons) and any("120-minute" in r for r in reasons)


# ---------------------------------------------------------------------------
# local Google Drive for desktop folder
# ---------------------------------------------------------------------------
def _local_client(tmp_path, **settings) -> tuple[StudentWorkstationClient, Path]:
    drive = tmp_path / "GoogleDrive"
    drive.mkdir(exist_ok=True)
    folder = drive / "alice-workstation"
    assign_folder(str(folder), "alice", artifact_dir=tmp_path / "artifacts", **settings)
    return StudentWorkstationClient(artifact_dir=tmp_path / "artifacts"), folder


def _publish(folder: Path, submission: dict, status: dict, archive: bytes | None) -> Path:
    job = folder / "jobs" / status["label"]
    (job / "input").mkdir(parents=True, exist_ok=True)
    pending = folder / "inbox" / submission["job_name"]
    if pending.exists():
        pending.rename(job / "input" / submission["job_name"])
    if archive is not None:
        (job / status["result_file"]).write_bytes(archive)
    (job / "status.json").write_text(json.dumps(status))
    return job


def test_local_submission_round_trip_and_failed_result(tmp_path):
    client, folder = _local_client(tmp_path, cores=4, memory_gb=8)
    assert client.preflight()["ready"] and "no workstation has reported" in client.preflight()["reason"]
    submission = client.submit(CALCULATION)
    inbox_job = folder / "inbox" / submission["job_name"]
    manifest = json.loads((inbox_job / "job.json").read_text())
    payload = (inbox_job / "calculation.json").read_bytes()
    assert manifest["engine"] == "cochem_base" and manifest["input"] == "calculation.json"
    assert manifest["job_id"] == submission["client_job_id"] and manifest["student_id"] == "alice"
    assert manifest["files"] == {"calculation.json": _sha(payload)}
    assert manifest["resources"] == {"cores": 4, "memory_gb": 8.0, "max_hours": 48}
    assert json.loads(payload)["engine"] == "pyscf"
    assert client.status(submission)["status"] == "queued"
    assert client.history() == [submission]

    label = submission["job_name"] + "__1a2b3c4d"
    _publish(folder, submission, _status(label=label, client_job_id=submission["client_job_id"],
                                         state="RUNNING"), None)
    assert client.status(submission)["status"] == "running"
    paused = _status(label=label, client_job_id=submission["client_job_id"], state="PAUSED")
    _publish(folder, submission, paused, None)
    assert "owner uses the machine" in client.status(submission)["detail"]
    # Terminal only once the archive is published.
    _publish(folder, submission, _status(label=label, client_job_id=submission["client_job_id"], state="FAILED"), None)
    assert client.status(submission)["status"] == "running"
    archive = _results_zip(client_job_id=submission["client_job_id"], calculation_sha256=_sha(payload))
    _publish(folder, submission, _status(label=label, client_job_id=submission["client_job_id"], state="FAILED",
                                         result=archive), archive)
    state = client.status(submission)
    assert state["status"] == "completed" and state["conclusion"] == "failure"
    retrieved = client.retrieve_results(submission)
    assert retrieved["report"]["status"] == "failed" and retrieved["report"]["operation_performed"] is False
    assert "cochem_base_run.log" in retrieved["files"]
    assert client.retrieve_results(submission)["report"] == retrieved["report"]  # retained, not re-downloaded
    assert client.status(submission)["conclusion"] == "failure"


def test_completed_job_without_base_execution_record_is_not_accepted(tmp_path):
    client, folder = _local_client(tmp_path)
    submission = client.submit(CALCULATION)
    payload = (folder / "inbox" / submission["job_name"] / "calculation.json").read_bytes()
    archive = _results_zip(client_job_id=submission["client_job_id"], calculation_sha256=_sha(payload),
                           summary={"state": "COMPLETED"})
    label = submission["job_name"] + "__00000001"
    _publish(folder, submission, _status(label=label, client_job_id=submission["client_job_id"], state="COMPLETED",
                                         result=archive), archive)
    report = client.retrieve_results(submission)["report"]
    assert report["status"] == "failed" and "not accepted" in report["message"]


@pytest.mark.parametrize("case", ["other-calculation", "other-client", "tampered", "unsafe-path", "partial-sync"])
def test_results_that_do_not_match_the_submission_are_rejected(tmp_path, case):
    client, folder = _local_client(tmp_path)
    submission = client.submit(CALCULATION)
    payload = (folder / "inbox" / submission["job_name"] / "calculation.json").read_bytes()
    sha, cid, extra = _sha(payload), submission["client_job_id"], {}
    if case == "other-calculation":
        sha = _sha(b"something else")
    if case == "other-client":
        cid = "cochem-base:" + str(uuid.uuid4())
    if case == "tampered":
        extra = {"base_output/result.json": b"{}", "base_output/result.json.sha256": ("0" * 64 + "  result.json\n").encode()}
    if case == "unsafe-path":
        extra = {"../../escape.txt": b"x"}
    archive = _results_zip(client_job_id=cid, calculation_sha256=sha, extra=extra)
    status = _status(label=submission["job_name"] + "__abcdef01", client_job_id=submission["client_job_id"],
                     state="FAILED", result=archive)
    if case == "partial-sync":
        status["result_sha256"] = "f" * 64
    _publish(folder, submission, status, archive)
    with pytest.raises(WorkstationQueueError):
        client.retrieve_results(submission)
    assert not (Path(client.jobs) / submission["request_id"] / "results").exists()


def test_omitted_transient_files_are_reported_not_rejected(tmp_path):
    client, folder = _local_client(tmp_path)
    submission = client.submit(CALCULATION)
    payload = (folder / "inbox" / submission["job_name"] / "calculation.json").read_bytes()
    extra = {"base_output/kept.txt": b"kept", "base_output/kept.txt.sha256": (_sha(b"kept") + "  kept.txt\n").encode(),
             "base_output/scratch.tmp.sha256": (_sha(b"x") + "  scratch.tmp\n").encode()}
    archive = _results_zip(client_job_id=submission["client_job_id"], calculation_sha256=_sha(payload), extra=extra)
    _publish(folder, submission, _status(label=submission["job_name"] + "__abcdef02",
                                         client_job_id=submission["client_job_id"], state="FAILED", result=archive),
             archive)
    assert client.retrieve_results(submission)["report"]["omitted_files"] == ["base_output/scratch.tmp"]


def test_cancel_pending_and_running(tmp_path):
    client, folder = _local_client(tmp_path)
    first = client.submit(CALCULATION)
    client.cancel(first)
    assert not (folder / "inbox" / first["job_name"]).exists()
    second = client.submit(CALCULATION)
    job = _publish(folder, second, _status(label=second["job_name"] + "__abcdef03",
                                           client_job_id=second["client_job_id"], state="RUNNING"), None)
    client.cancel(second)
    assert (job / "CANCEL").exists()


def test_tampered_local_record_is_refused(tmp_path):
    client, _folder = _local_client(tmp_path)
    submission = client.submit(CALCULATION)
    request = Path(client.jobs) / submission["request_id"] / "request.json"
    request.chmod(0o600)
    request.write_bytes(request.read_bytes().replace(b"pyscf", b"orca!"))
    with pytest.raises(WorkstationQueueError, match="changed"):
        client.status(submission)


def test_health_is_read_from_the_folder_and_its_class_folder(tmp_path):
    client, folder = _local_client(tmp_path)
    status_dir = folder.parent / "_status"
    status_dir.mkdir()
    health = {"schema": "cochem.workstation-health/1", "node_id": "lab-ws", "updated_epoch": int(time.time()),
              "stale_after_seconds": 600, "accepting_jobs": True, "mode": "away",
              "capacity": {"cores_available_for_jobs": 14}, "queue": {"QUEUED": 1}}
    (status_dir / "workstation_health.lab-ws.json").write_text(json.dumps(health))
    result = client.preflight()
    assert result["ready"] and "lab-ws is accepting jobs" in result["reason"] and "14 cores" in result["reason"]


def test_open_shell_orca_needs_t9_like_every_other_route(tmp_path):
    client, _folder = _local_client(tmp_path)
    with pytest.raises(ValueError, match="T9"):
        client.submit(dict(CALCULATION, engine="orca", method="UHF", basis_set="def2-SVP", multiplicity=3))


# ---------------------------------------------------------------------------
# Google Drive API (Codespaces / Actions): real loopback server
# ---------------------------------------------------------------------------
FOLDER = "application/vnd.google-apps.folder"
CLAUSE = re.compile(r"'((?:[^'\\]|\\.)*)' in parents|name (=|contains) '((?:[^'\\]|\\.)*)'|"
                    r"mimeType (=|!=) '((?:[^'\\]|\\.)*)'|trashed = false")


def _unescape(value: str) -> str:
    return re.sub(r"\\(.)", r"\1", value)


class FakeDrive:
    """In-memory Drive with the v3 endpoints BASE uses; checks real RS256 assertions."""

    def __init__(self, public_key) -> None:
        self.public_key = public_key
        self.files: dict[str, dict] = {}
        self.token = "token-" + uuid.uuid4().hex
        self.fail_next = 0
        self.quota = False
        self.add("SharedDriveRoot0001", "Class folder", FOLDER, None)
        self.add("AliceFolder000001", "alice-workstation", FOLDER, "SharedDriveRoot0001")

    def add(self, file_id, name, mime, parent, content=b"") -> dict:
        record = {"id": file_id, "name": name, "mimeType": mime, "parents": [parent] if parent else [],
                  "content": content}
        self.files[file_id] = record
        return record

    def children(self, parent: str) -> list[dict]:
        return [f for f in self.files.values() if parent in f["parents"]]

    def find(self, parent: str, name: str) -> dict | None:
        return next((f for f in self.children(parent) if f["name"] == name), None)

    def query(self, q: str) -> list[dict]:
        remainder = CLAUSE.sub("", q).replace(" and ", "").strip()
        assert not remainder, f"unsupported query part {remainder!r}"
        result = list(self.files.values())
        for match in CLAUSE.finditer(q):
            if match[1] is not None:
                result = [f for f in result if _unescape(match[1]) in f["parents"]]
            elif match[2] == "=":
                result = [f for f in result if f["name"] == _unescape(match[3])]
            elif match[2] == "contains":
                result = [f for f in result if f["name"].startswith(_unescape(match[3]))]
            elif match[4] == "=":
                result = [f for f in result if f["mimeType"] == _unescape(match[5])]
            elif match[4] == "!=":
                result = [f for f in result if f["mimeType"] != _unescape(match[5])]
        return result

    def serve(self):
        drive = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def reply(self, code: int, body: bytes | dict = b"", content_type="application/json"):
                data = json.dumps(body).encode() if isinstance(body, dict) else body
                self.send_response(code)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def body(self) -> bytes:
                return self.rfile.read(int(self.headers.get("Content-Length", 0)))

            def handle_any(self, method: str):
                url = urllib.parse.urlparse(self.path)
                params = dict(urllib.parse.parse_qsl(url.query))
                data = self.body()
                if url.path == "/token":
                    form = dict(urllib.parse.parse_qsl(data.decode()))
                    header, claims, signature = form["assertion"].split(".")
                    from cryptography.hazmat.primitives import hashes
                    from cryptography.hazmat.primitives.asymmetric import padding
                    pad = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))  # noqa: E731
                    drive.public_key.verify(pad(signature), f"{header}.{claims}".encode(), padding.PKCS1v15(),
                                            hashes.SHA256())
                    payload = json.loads(pad(claims))
                    assert payload["scope"] == "https://www.googleapis.com/auth/drive"
                    assert payload["aud"].endswith("/token") and payload["exp"] > payload["iat"]
                    return self.reply(200, {"access_token": drive.token, "expires_in": 3600})
                if self.headers.get("Authorization") != "Bearer " + drive.token:
                    return self.reply(401, {"error": "unauthenticated"})
                if params.get("supportsAllDrives") != "true":
                    return self.reply(400, {"error": "shared drives not supported by this call"})
                if drive.fail_next:
                    drive.fail_next -= 1
                    return self.reply(503, {"error": "backend error"})
                parts = url.path.split("/")
                file_id = parts[4] if len(parts) > 4 else None
                upload = url.path.startswith("/upload/")
                if method == "GET" and file_id is None:
                    found = drive.query(params["q"])
                    return self.reply(200, {"files": [{k: v for k, v in f.items() if k in {"id", "name", "mimeType"}}
                                                      | {"size": str(len(f["content"]))} for f in found]})
                if method == "GET":
                    record = drive.files.get(file_id)
                    if record is None:
                        return self.reply(404, {"error": "notFound"})
                    if params.get("alt") == "media":
                        return self.reply(200, record["content"], "application/octet-stream")
                    return self.reply(200, {k: v for k, v in record.items() if k != "content"})
                if method == "DELETE":
                    stack = [file_id]
                    while stack:
                        current = stack.pop()
                        stack += [f["id"] for f in drive.children(current)]
                        drive.files.pop(current, None)
                    return self.reply(204, b"")
                if method == "PATCH" and upload:
                    drive.files[file_id]["content"] = data
                    return self.reply(200, {"id": file_id})
                if method == "PATCH":
                    drive.files[file_id]["name"] = json.loads(data)["name"]
                    return self.reply(200, {"id": file_id})
                if method == "POST" and upload:
                    if drive.quota:
                        return self.reply(403, {"error": {"reason": "storageQuotaExceeded",
                                                          "message": "Service Accounts do not have storage quota."}})
                    boundary = re.search(r"boundary=(\S+)", self.headers["Content-Type"])[1].encode()
                    sections = [p for p in data.split(b"--" + boundary) if p.strip() not in {b"", b"--"}]
                    metadata = json.loads(sections[0].split(b"\r\n\r\n", 1)[1].strip())
                    content = sections[1].split(b"\r\n\r\n", 1)[1][:-2]
                    new = drive.add(uuid.uuid4().hex, metadata["name"], "application/octet-stream",
                                    metadata["parents"][0], content)
                    return self.reply(200, {"id": new["id"]})
                if method == "POST":
                    metadata = json.loads(data)
                    new = drive.add(uuid.uuid4().hex, metadata["name"], metadata.get("mimeType", ""),
                                    metadata["parents"][0])
                    return self.reply(200, {"id": new["id"]})
                return self.reply(405, {"error": "unsupported"})

            def do_GET(self):
                self.handle_any("GET")

            def do_POST(self):
                self.handle_any("POST")

            def do_PATCH(self):
                self.handle_any("PATCH")

            def do_DELETE(self):
                self.handle_any("DELETE")

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server


@pytest.fixture
def drive():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    fake = FakeDrive(key.public_key())
    server = fake.serve()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    credentials = {"type": "service_account", "client_email": "cochem@lab.iam.gserviceaccount.com",
                   "private_key": key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                    serialization.NoEncryption()).decode(),
                   "token_uri": base + "/token"}

    def transport(folder_id="AliceFolder000001"):
        return DriveApiTransport(folder_id, credentials=credentials, api_url=base + "/drive/v3",
                                 upload_url=base + "/upload/drive/v3", allow_loopback=True, timeout=10)

    yield fake, transport
    server.shutdown()


def test_drive_folder_link_round_trip(tmp_path, drive):
    fake, transport = drive
    link = "https://drive.google.com/drive/folders/AliceFolder000001"
    assign_folder(link, "alice", artifact_dir=tmp_path / "artifacts", transport=transport())
    inbox, jobs = fake.find("AliceFolder000001", "inbox"), fake.find("AliceFolder000001", "jobs")
    assert inbox and jobs and json.loads(fake.find("AliceFolder000001", FOLDER_MARKER)["content"])["student_id"] == "alice"
    assign_folder(link, "alice", artifact_dir=tmp_path / "artifacts", transport=transport())  # idempotent
    assert len([f for f in fake.children("AliceFolder000001") if f["name"] == "inbox"]) == 1

    client = StudentWorkstationClient(artifact_dir=tmp_path / "artifacts", transport=transport())
    assert client.settings.transport == "drive_api"
    fake.fail_next = 1  # a transient Google error is retried
    submission = client.submit(CALCULATION)
    job = fake.find(inbox["id"], submission["job_name"])
    assert job is not None and not any(f["name"].startswith(".cochem-upload") for f in fake.children(inbox["id"]))
    payload = fake.find(job["id"], "calculation.json")["content"]
    manifest = json.loads(fake.find(job["id"], "job.json")["content"])
    assert manifest["files"] == {"calculation.json": _sha(payload)} and manifest["engine"] == "cochem_base"
    assert client.status(submission)["status"] == "queued"

    # The workstation (through Drive for desktop) picks it up and later publishes results.
    label = submission["job_name"] + "__0badcafe"
    job_folder = fake.add("JobFolder0000001", label, FOLDER, jobs["id"])
    fake.files.pop(job["id"])
    archive = _results_zip(client_job_id=submission["client_job_id"], calculation_sha256=_sha(payload))
    fake.add("StatusFile000001", "status.json", "application/json", job_folder["id"],
             json.dumps(_status(label=label, client_job_id=submission["client_job_id"], state="RUNNING")).encode())
    assert client.status(submission)["status"] == "running"
    fake.files["StatusFile000001"]["content"] = json.dumps(_status(
        label=label, client_job_id=submission["client_job_id"], state="FAILED", result=archive)).encode()
    fake.add("ResultZip0000001", f"{label}_results.zip", "application/zip", job_folder["id"], archive)
    assert client.status(submission)["conclusion"] == "failure"
    report = client.retrieve_results(submission)["report"]
    assert report["status"] == "failed" and report["workstation_state"] == "FAILED"

    # Health is found in the class folder that contains the user's folder.
    status_dir = fake.add("StatusFolder0001", "_status", FOLDER, "SharedDriveRoot0001")
    health = {"schema": "cochem.workstation-health/1", "node_id": "lab-ws", "updated_epoch": int(time.time()),
              "stale_after_seconds": 600, "accepting_jobs": True, "mode": "present",
              "capacity": {"cores_available_for_jobs": 6}, "queue": {}}
    fake.add("HealthFile000001", "workstation_health.lab-ws.json", "application/json", status_dir["id"],
             json.dumps(health).encode())
    assert "6 cores" in client.preflight()["reason"]


def test_drive_cancel_pending_and_running(tmp_path, drive):
    fake, transport = drive
    assign_folder("drive:AliceFolder000001", "alice", artifact_dir=tmp_path / "artifacts", transport=transport())
    client = StudentWorkstationClient(artifact_dir=tmp_path / "artifacts", transport=transport())
    inbox, jobs = fake.find("AliceFolder000001", "inbox"), fake.find("AliceFolder000001", "jobs")
    pending = client.submit(CALCULATION)
    client.cancel(pending)
    assert fake.find(inbox["id"], pending["job_name"]) is None
    running = client.submit(CALCULATION)
    label = running["job_name"] + "__abc12345"
    job_folder = fake.add("JobFolder0000002", label, FOLDER, jobs["id"])
    fake.add("StatusFile000002", "status.json", "application/json", job_folder["id"],
             json.dumps(_status(label=label, client_job_id=running["client_job_id"], state="RUNNING")).encode())
    client.cancel(running)
    assert fake.find(job_folder["id"], "CANCEL") is not None


def test_drive_errors_are_explained(tmp_path, drive):
    fake, transport = drive
    with pytest.raises(WorkstationQueueError, match="not shared"):
        assign_folder("drive:MissingFolder0001", "alice", artifact_dir=tmp_path / "a", transport=transport("MissingFolder0001"))
    fake.quota = True
    with pytest.raises(WorkstationQueueError, match="shared drive"):
        assign_folder("drive:AliceFolder000001", "alice", artifact_dir=tmp_path / "a", transport=transport())
    with pytest.raises(WorkstationQueueError, match="HTTPS"):
        DriveApiTransport("AliceFolder000001", access_token="x", api_url="http://127.0.0.1:1/drive/v3")
    with pytest.raises(WorkstationQueueError, match="Google's API"):
        DriveApiTransport("AliceFolder000001", access_token="x", api_url="https://evil.example.com/drive/v3")


def test_drive_link_without_credentials_explains_the_secret(tmp_path):
    previous = {key: os.environ.pop(key, None) for key in ("COCHEM_WORKSTATION_DRIVE_TOKEN",
                "COCHEM_WORKSTATION_DRIVE_CREDENTIALS", "COCHEM_WORKSTATION_DRIVE_CREDENTIALS_FILE",
                "GOOGLE_APPLICATION_CREDENTIALS")}
    try:
        settings = WorkstationSettings(folder="drive:AliceFolder000001", student_id="alice")
        client = StudentWorkstationClient(artifact_dir=tmp_path / "artifacts", settings=settings)
        result = client.preflight()
        assert not result["ready"] and "COCHEM_WORKSTATION_DRIVE_CREDENTIALS" in result["reason"]
    finally:
        os.environ.update({k: v for k, v in previous.items() if v is not None})


def test_unassigned_route_is_not_ready(tmp_path):
    client = StudentWorkstationClient(artifact_dir=tmp_path / "artifacts", settings=None)
    assert client.preflight() == {"ready": False, "workstations": [],
                                  "reason": "Assign your workstation Drive folder first (Workstation settings)"}
    with pytest.raises(WorkstationQueueError):
        client.submit(CALCULATION)


def test_local_transport_requires_an_assigned_folder(tmp_path):
    with pytest.raises(WorkstationQueueError, match="missing inbox"):
        LocalFolderTransport(tmp_path).submit("base-x", {"calculation.json": b"{}"})
