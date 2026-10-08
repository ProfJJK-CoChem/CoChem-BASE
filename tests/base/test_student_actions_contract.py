"""Transport/integrity acceptance, without inventing scientific calculations."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import secrets
import stat
import subprocess
import sys
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from cochem_base.interfaces.student_actions import (
    StudentActionsClient,
    StudentActionsError,
    _extract_verified_archive,
    verify_retained_results,
)
from cochem_base.interfaces.student_request import canonical_json, decode_request, encode_request


class ProjectApprovalServer(ThreadingHTTPServer):
    """Actual local REST exchange for approval metadata, never science output."""

    def __init__(self):
        super().__init__(("127.0.0.1", 0), ProjectApprovalHandler)
        self.token = secrets.token_urlsafe(32)
        self.revision = "b" * 40
        self.variables = {"COCHEM_APPROVED_BASE_SHA": self.revision}
        self.variable_status = 200
        self.variable_name_changed = False
        self.commit_changed = False
        self.channel_changed = False
        self.worker_missing = False
        self.paths = []
        self.metadata_auth_verified = False


class ProjectApprovalHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return None

    def do_GET(self):
        peer = self.server
        peer.paths.append(self.path)
        if self.headers.get("Authorization") != "Bearer " + peer.token:
            self.answer({}, 401)
            return
        prefix = "/repos/student/project"
        if self.path == prefix:
            self.answer({"full_name": "student/project", "private": True,
                         "owner": {"type": "User", "login": "student"},
                         "default_branch": "main", "permissions": {"push": True},
                         "fork": False, "archived": False, "disabled": False})
        elif self.path == prefix + "/actions/workflows/student_research.yml":
            self.answer({"id": 123, "state": "active"})
        elif self.path == prefix + "/commits/main":
            self.answer({"sha": "a" * 40})
        elif self.path.startswith(prefix + "/actions/variables/"):
            peer.metadata_auth_verified = True
            name = self.path.rsplit("/", 1)[1]
            if peer.variable_status != 200:
                self.answer({"message": "Engineering access refused"}, peer.variable_status)
            elif name not in peer.variables:
                self.answer({}, 404)
            else:
                self.answer({"name": "wrong-variable" if peer.variable_name_changed else name,
                             "value": peer.variables[name]})
        elif self.path.startswith("/repos/ProfJJK-CoChem/CoChem-BASE/commits/"):
            self.answer({"sha": "c" * 40 if peer.commit_changed else peer.revision})
        elif self.path == "/repos/ProfJJK-CoChem/CoChem-BASE/contents/.cochem/course-channels/research.json":
            course = {"schema_version": "cochem.course-approval/1", "repository": "ProfJJK-CoChem/CoChem-BASE",
                      "approved_base_revision": "not-a-commit" if peer.channel_changed else peer.revision}
            self.answer({"type": "file", "encoding": "base64",
                         "content": base64.b64encode(canonical_json(course)).decode()})
        elif self.path == "/repos/ProfJJK-CoChem/CoChem-BASE/contents/scripts/run_student_research.py?ref=" + peer.revision:
            self.answer({"type": "file"}, 404 if peer.worker_missing else 200)
        else:
            self.answer({"message": "Unexpected engineering endpoint"}, 404)

    def answer(self, payload, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(canonical_json(payload))


@pytest.fixture
def project_approval_peer():
    peer = ProjectApprovalServer()
    thread = Thread(target=peer.serve_forever, daemon=True)
    thread.start()
    try:
        yield peer
    finally:
        peer.shutdown()
        peer.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def project_approval_client(peer, tmp_path):
    return StudentActionsClient("student/project", token=peer.token, repository_root=tmp_path,
                                api_url=f"http://127.0.0.1:{peer.server_port}", allow_loopback=True)


def test_current_target_approval_is_used_instead_of_latest_main(project_approval_peer, tmp_path):
    peer = project_approval_peer
    client = project_approval_client(peer, tmp_path)
    selected = client.preflight()
    assert selected["worker_source_sha"] == peer.revision
    assert selected["worker_approval"] == "instructor-actions-variable"
    assert peer.metadata_auth_verified
    assert not any("secrets" in path or path.endswith("/commits/main") and "CoChem-BASE" in path
                   for path in peer.paths)
    # Instructor maintenance changes existing projects without restarting a GUI.
    peer.revision = "d" * 40
    peer.variables["COCHEM_APPROVED_BASE_SHA"] = peer.revision
    assert client.preflight()["worker_source_sha"] == peer.revision


def test_target_course_channel_resolves_exact_canonical_approval(project_approval_peer, tmp_path):
    peer = project_approval_peer
    peer.variables = {"COCHEM_COURSE_CHANNEL": ".cochem/course-channels/research.json"}
    selected = project_approval_client(peer, tmp_path).preflight()
    assert selected["worker_source_sha"] == peer.revision
    assert selected["worker_approval"] == "instructor-course-channel"
    assert not any(path.endswith("/commits/main") and "CoChem-BASE" in path for path in peer.paths)


@pytest.mark.parametrize("status", [401, 403, 422])
def test_target_approval_denial_never_falls_back_to_main(project_approval_peer, tmp_path, status):
    peer = project_approval_peer
    peer.variable_status = status
    with pytest.raises(StudentActionsError, match="course approval could not be read") as refused:
        project_approval_client(peer, tmp_path).preflight()
    assert refused.value.http_status == status
    assert not any("/repos/ProfJJK-CoChem/CoChem-BASE/" in path for path in peer.paths)


@pytest.mark.parametrize("revision", ["main", "b" * 39, "b" * 40 + "\n", 3])
def test_invalid_target_worker_approval_refuses_before_source_read(project_approval_peer, tmp_path, revision):
    peer = project_approval_peer
    peer.variables["COCHEM_APPROVED_BASE_SHA"] = revision
    with pytest.raises(StudentActionsError, match="invalid"):
        project_approval_client(peer, tmp_path).preflight()
    assert not any("/repos/ProfJJK-CoChem/CoChem-BASE/" in path for path in peer.paths)


@pytest.mark.parametrize("flag", ["variable_name_changed", "commit_changed", "worker_missing"])
def test_changed_target_approval_or_missing_exact_worker_refuses(project_approval_peer, tmp_path, flag):
    peer = project_approval_peer
    setattr(peer, flag, True)
    with pytest.raises(StudentActionsError):
        project_approval_client(peer, tmp_path).preflight()
    assert not any(path.endswith("/commits/main") and "CoChem-BASE" in path for path in peer.paths)


@pytest.mark.parametrize("channel", ["main", "../escape.json", ".cochem/course-channels/research.json?ref=evil"])
def test_project_course_channel_is_data_only(project_approval_peer, tmp_path, channel):
    peer = project_approval_peer
    peer.variables = {"COCHEM_COURSE_CHANNEL": channel}
    with pytest.raises(StudentActionsError, match="canonical BASE approval data"):
        project_approval_client(peer, tmp_path).preflight()
    assert not any("/repos/ProfJJK-CoChem/CoChem-BASE/" in path for path in peer.paths)


def test_project_channel_invalid_revision_refuses_without_latest_fallback(project_approval_peer, tmp_path):
    peer = project_approval_peer
    peer.variables = {"COCHEM_COURSE_CHANNEL": ".cochem/course-channels/research.json"}
    peer.channel_changed = True
    with pytest.raises(StudentActionsError, match="immutable approved BASE revision"):
        project_approval_client(peer, tmp_path).preflight()
    assert not any("/commits/" in path and "CoChem-BASE" in path for path in peer.paths)


@pytest.mark.parametrize("api_url,allow_loopback", [("https://example.com", False),
                                                   ("http://127.0.0.1:1234", False),
                                                   ("http://user@127.0.0.1:1234", True)])
def test_approval_transport_does_not_forward_identity_to_other_hosts(tmp_path, api_url, allow_loopback):
    with pytest.raises(ValueError, match="GitHub's verified HTTPS"):
        StudentActionsClient("student/project", token="local-engineering-only", repository_root=tmp_path,
                             api_url=api_url, allow_loopback=allow_loopback)


def _request():
    return {"schema_version": "cochem.student-request/1",
            "request_id": "2b95b278-bc3c-42c0-8143-dd601350af96",
            "repository": "ProfJJK-CoChem/CoChem-BASE", "source_sha": "a" * 40,
            "worker_source_sha": "b" * 40,
            "submitted_at": "2026-10-08T00:00:00+00:00",
            "resources": {"cores": 2, "maxcore_mb": 512},
            "calculation": {"engine": "xtb", "method": "GFN2-xTB", "basis_set": None,
                            "geometry": "2\ntransport-only structure\nH 0 0 0\nH 0 0 0.74\n",
                            "timeout_seconds": 60}, "provider": None, "capability_probe": None,
            "scientific_inputs": None, "data_inputs": None, "t9_request": None, "files": {}}


def _archive(request, *, change_report=False, extra_path=None, corrupt_file=False, false_completion=False):
    contents = canonical_json(request)
    identity = {key: request[key] for key in ("request_id", "repository", "source_sha", "worker_source_sha")}
    identity.update(payload_sha256=hashlib.sha256(contents).hexdigest(), run_id=123, run_attempt=1)
    submission = {**identity, "workflow_id": 456, "branch": "main"}
    report = {"schema_version": "cochem.student-result/1", **identity,
              "status": "failed", "operation_performed": False,
              "error": "Transport-only fixture; no chemistry was executed"}
    if change_report:
        report["request_id"] = "d376a57a-63e3-443a-8bc1-6a238d985c20"
    if false_completion:
        report["status"] = "completed"
    files = {"request.json": contents + b"\n", "student-result.json": canonical_json(report) + b"\n"}
    inventory = {name: {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)} for name, data in files.items()}
    manifest = {"schema_version": "cochem.student-publication/1", **identity, "files": inventory}
    if corrupt_file:
        files["request.json"] += b" "
    files["publication-manifest.json"] = canonical_json(manifest)
    if extra_path:
        files[extra_path] = b"unlisted"
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return result.getvalue(), submission


def test_exact_request_bytes_and_sha_roundtrip():
    request = _request()
    encoded, digest = encode_request(request)
    assert decode_request(encoded, digest) == request
    assert base64.b64decode(encoded) == canonical_json(request)


def test_request_tamper_is_rejected():
    encoded, digest = encode_request(_request())
    changed = bytearray(base64.b64decode(encoded))
    changed[-2] ^= 1
    with pytest.raises(ValueError, match="SHA-256"):
        decode_request(base64.b64encode(changed).decode(), digest)


@pytest.mark.parametrize("field,value", [("cores", True), ("cores", 3), ("maxcore_mb", 0), ("maxcore_mb", 1025)])
def test_finite_worker_allocation_is_enforced(field, value):
    request = _request()
    request["resources"][field] = value
    with pytest.raises(ValueError):
        encode_request(request)


def test_nonfinite_geometry_is_rejected():
    request = _request()
    request["calculation"]["geometry"] = "1\ninvalid\nH nan 0 0\n"
    with pytest.raises(ValueError, match="finite"):
        encode_request(request)


def test_uploaded_file_hash_is_bound():
    request = _request()
    contents = request["calculation"]["geometry"].encode()
    request["files"] = {"inputs/geometry.xyz": {"content_base64": base64.b64encode(contents).decode(),
                         "sha256": "0" * 64, "size_bytes": len(contents)}}
    with pytest.raises(ValueError, match="integrity"):
        encode_request(request)


@pytest.mark.parametrize("name", ["../escape.xyz", "/absolute.xyz", "inputs/../escape.xyz", "inputs\\escape.xyz", "C:escape.xyz", "inputs/CON.xyz", "inputs/trailing. "])
def test_input_path_escape_is_rejected(name):
    request = _request()
    contents = b"1\ninput\nH 0 0 0\n"
    request["files"] = {name: {"content_base64": base64.b64encode(contents).decode(),
                              "sha256": hashlib.sha256(contents).hexdigest(), "size_bytes": len(contents)}}
    with pytest.raises(ValueError):
        encode_request(request)


def test_duplicate_json_fields_are_rejected():
    raw = canonical_json(_request())
    raw = b'{"schema_version":"cochem.student-request/1",' + raw[1:]
    with pytest.raises(ValueError, match="Duplicate"):
        decode_request(base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest())


def test_verified_failure_evidence_is_imported_without_claiming_science(tmp_path):
    contents, submission = _archive(_request())
    destination = tmp_path / "results"
    result = _extract_verified_archive(contents, destination, submission, submission)
    assert result["report"]["operation_performed"] is False
    assert result["report"]["status"] == "failed"
    assert result["request_id"] == submission["request_id"]
    assert json.loads((destination / "request.json").read_bytes()) == _request()


def test_retained_results_reopen_offline_and_reject_later_tampering(tmp_path):
    contents, submission = _archive(_request())
    destination = tmp_path / "results"
    downloaded = _extract_verified_archive(contents, destination, submission, submission)
    reopened = verify_retained_results(destination, submission)
    assert reopened == downloaded
    report = destination / "student-result.json"
    report.write_bytes(report.read_bytes() + b" ")
    with pytest.raises(StudentActionsError, match="integrity"):
        verify_retained_results(destination, submission)


def test_retained_results_reject_new_symlink_and_missing_attempt_receipt(tmp_path):
    contents, submission = _archive(_request())
    destination = tmp_path / "results"
    _extract_verified_archive(contents, destination, submission, submission)
    with pytest.raises(StudentActionsError, match="attempt"):
        verify_retained_results(destination, {**submission, "run_attempt": None})
    (destination / "redirect").symlink_to(tmp_path)
    with pytest.raises(StudentActionsError, match="links"):
        verify_retained_results(destination, submission)


@pytest.mark.parametrize("option", ["change_report", "corrupt_file"])
def test_result_identity_or_file_tamper_is_rejected_atomically(tmp_path, option):
    contents, submission = _archive(_request(), **{option: True})
    destination = tmp_path / "results"
    with pytest.raises(StudentActionsError):
        _extract_verified_archive(contents, destination, submission, submission)
    assert not destination.exists()
    assert not list(tmp_path.glob(".cochem-result-*"))


@pytest.mark.parametrize("name", ["../escape", "extra.txt", "nested\\escape", "/absolute"])
def test_result_unlisted_or_escaping_files_are_rejected(tmp_path, name):
    contents, submission = _archive(_request(), extra_path=name)
    with pytest.raises((StudentActionsError, ValueError)):
        _extract_verified_archive(contents, tmp_path / "results", submission, submission)
    assert not (tmp_path / "results").exists()


def test_result_symlink_is_rejected(tmp_path):
    contents, submission = _archive(_request())
    updated = io.BytesIO(contents)
    with zipfile.ZipFile(updated, "a") as archive:
        member = zipfile.ZipInfo("redirect")
        member.create_system = 3
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(member, "/tmp/elsewhere")
    with pytest.raises(StudentActionsError, match="links"):
        _extract_verified_archive(updated.getvalue(), tmp_path / "results", submission, submission)


def test_result_import_preserves_existing_directory(tmp_path):
    contents, submission = _archive(_request())
    existing = tmp_path / "results"
    existing.mkdir()
    marker = existing / "student-notes.txt"
    marker.write_text("keep my work")
    with pytest.raises(StudentActionsError, match="existing"):
        _extract_verified_archive(contents, existing, submission, submission)
    assert marker.read_text() == "keep my work"


def test_false_completion_without_worker_approval_is_rejected(tmp_path):
    contents, submission = _archive(_request(), false_completion=True)
    with pytest.raises(StudentActionsError):
        _extract_verified_archive(contents, tmp_path / "results", submission, submission)
    assert not (tmp_path / "results").exists()


def test_worker_and_assignment_source_are_independently_bound(tmp_path):
    contents, submission = _archive(_request())
    submission["worker_source_sha"] = "c" * 40
    with pytest.raises(StudentActionsError, match="provenance"):
        _extract_verified_archive(contents, tmp_path / "results", submission, submission)
    assert not (tmp_path / "results").exists()


def test_capability_probe_has_no_geometry_or_chemistry_request():
    request = _request()
    request.update(calculation=None, capability_probe={"engines": ["orca", "cfour"]})
    encoded, digest = encode_request(request)
    assert decode_request(encoded, digest)["calculation"] is None
    assert decode_request(encoded, digest)["provider"] is None


def test_capability_probe_rejects_arbitrary_engine_or_input():
    request = _request()
    request.update(calculation=None, capability_probe={"engines": ["unreviewed-engine"]})
    with pytest.raises(ValueError, match="readiness"):
        encode_request(request)


def test_t9_cannot_choose_a_worker_executable():
    request = _request()
    request["calculation"]["engine"] = "orca"
    request["t9_request"] = {"pyscf_version": "2.14.0", "method": "NEVPT2", "basis": "STO-3G",
                             "active_electrons": 2, "active_orbitals": [0],
                             "active_space_rationale": "Explicit closed-shell occupied orbital",
                             "threads": 1, "memory_mb": 128, "timeout_seconds": 60, "max_cycle": 100,
                             "python_executable": "/unreviewed/python"}
    with pytest.raises(ValueError, match="executable"):
        encode_request(request)


def test_open_shell_orca_requires_portable_t9_science_without_executable_path():
    request = _request()
    request["calculation"].update(engine="orca", method="UHF", basis_set="6-31g", multiplicity=2,
        geometry="3\nStarting H3 input\nH 0 0 0\nH 0 0 0.9\nH 0.7 0 1.4\n")
    with pytest.raises(ValueError, match="explicit portable T9 active space"):
        encode_request(request)
    request["t9_request"] = {"pyscf_version": "2.14.0", "method": "NEVPT2", "basis": "6-31g",
        "active_electrons": 3, "active_orbitals": [0, 1, 2],
        "active_space_rationale": "All three 1s-derived MOs and three electrons of neutral H3",
        "threads": 1, "memory_mb": 128, "timeout_seconds": 60, "max_cycle": 100}
    encoded, digest = encode_request(request)
    accepted = decode_request(encoded, digest)
    assert accepted["t9_request"] == request["t9_request"]
    assert "python_executable" not in accepted["t9_request"]


def test_t9_recovery_cannot_exceed_the_job_allocation():
    request = _request()
    request["calculation"]["engine"] = "orca"
    request["t9_request"] = {"pyscf_version": "2.14.0", "method": "NEVPT2", "basis": "STO-3G",
                             "active_electrons": 2, "active_orbitals": [0],
                             "active_space_rationale": "Explicit closed-shell occupied orbital",
                             "threads": 3, "memory_mb": 128, "timeout_seconds": 60, "max_cycle": 100}
    with pytest.raises(ValueError, match="allocation"):
        encode_request(request)


def test_windows_xyz_bom_is_accepted_without_changing_uploaded_identity():
    request = _request()
    original = b"\xef\xbb\xbf" + request["calculation"]["geometry"].encode("utf-8")
    digest = hashlib.sha256(original).hexdigest()
    request["files"] = {"inputs/student-original.xyz": {"content_base64": base64.b64encode(original).decode(),
                        "sha256": digest, "size_bytes": len(original)}}
    encoded, request_digest = encode_request(request)
    decoded = decode_request(encoded, request_digest)
    saved = decoded["files"]["inputs/student-original.xyz"]
    assert base64.b64decode(saved["content_base64"]) == original
    assert saved["sha256"] == digest


def _scientific_request():
    request = _request()
    request["calculation"]["engine"] = "orca"
    request["scientific_inputs"] = {
        "schema_version": "cochem.scientific-input-transport/1", "kind": "read_hessian",
        "entrypoint": "native/reference.hess", "bundle_sha256": "c" * 64,
        "bundle_size_bytes": 1024,
        "geometry_sha256": hashlib.sha256(request["calculation"]["geometry"].encode()).hexdigest(),
        "blob_sha": "d" * 40, "commit_sha": "e" * 40,
        "branch": "cochem-input-" + request["request_id"],
        "path": f".cochem/submissions/{request['request_id']}/scientific-inputs.zip"}
    return request


def test_sealed_native_evidence_is_bound_to_request_geometry_and_data_path():
    request = _scientific_request()
    encoded, digest = encode_request(request)
    assert decode_request(encoded, digest)["scientific_inputs"] == request["scientific_inputs"]


@pytest.mark.parametrize("field,value", [("geometry_sha256", "f" * 64),
                                        ("path", ".github/workflows/replace.yml"),
                                        ("branch", "main"),
                                        ("bundle_size_bytes", 16 * 1024 * 1024 + 1)])
def test_native_evidence_cannot_change_geometry_source_branch_or_size(field, value):
    request = _scientific_request()
    request["scientific_inputs"][field] = value
    with pytest.raises(ValueError, match="provenance"):
        encode_request(request)


def test_primary_and_t9_recovery_share_one_finite_time_budget():
    request = _request()
    request["calculation"].update(engine="orca", timeout_seconds=1200)
    request["t9_request"] = {"pyscf_version": "2.14.0", "method": "NEVPT2", "basis": "STO-3G",
                             "active_electrons": 2, "active_orbitals": [0],
                             "active_space_rationale": "Explicit closed-shell occupied orbital",
                             "threads": 1, "memory_mb": 128, "timeout_seconds": 601, "max_cycle": 100}
    with pytest.raises(ValueError, match="allocation"):
        encode_request(request)


def test_preinstallation_worker_probe_uses_only_reviewed_checkout_and_stdlib(tmp_path):
    worker = Path(__file__).resolve().parents[2] / "scripts/run_student_research.py"
    program = ("import runpy; runpy.run_path(" + repr(str(worker)) + ",run_name='worker_import_only'); "
               "from scripts.probe_student_engines import probe_engines; "
               "r=probe_engines(['orca','cfour']); "
               "assert r['installed'] is False and r['scientific_execution_performed'] is False; "
               "assert all(not item['provisionable'] for item in r['engines'].values())")
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "COCHEM_ORCA_ASSET_CREDENTIAL", "COCHEM_CFOUR_ASSET_CREDENTIAL"}}
    completed = subprocess.run([sys.executable, "-B", "-I", "-S", "-c", program], env=environment,
                               cwd=tmp_path, capture_output=True, text=True, timeout=30, check=False)
    assert completed.returncode == 0, completed.stderr
