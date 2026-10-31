"""Transport/integrity acceptance, without inventing scientific calculations."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import runpy
import tempfile
import urllib.parse
import secrets
import signal
import stat
import subprocess
import sys
import uuid
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread, Event

import pytest

from cochem_base.interfaces.student_actions import (
    StudentActionsClient,
    StudentActionsError,
    _extract_verified_archive,
    verify_retained_results,
)
from cochem_base.interfaces.student_request import canonical_json, decode_request, encode_request


# Reuse real local Git/HTTP fixture code, never a fake scientific executor.
_ADMISSION_FIXTURES = runpy.run_path(str(Path(__file__).with_name('test_student_actions_admission.py')),
                                  run_name='canonical_admission_fixture')
AdmissionGitHandler = _ADMISSION_FIXTURES['GitHandler']
AdmissionGitStore = _ADMISSION_FIXTURES['GitStore']
_SMART_FIXTURES = runpy.run_path(str(Path(__file__).with_name('test_student_actions_admission_git_readonly.py')),
                              run_name='canonical_smart_git_fixture')
from cochem_base.interfaces import student_actions_admission as admission_contract


class ProjectApprovalServer(ThreadingHTTPServer):
    """Actual local REST exchange for approval metadata, never science output."""

    def __init__(self, *, variable_name_changed: bool = False,
                 commit_changed: bool = False, worker_missing: bool = False,
                 repository: str = "student/project"):
        super().__init__(("127.0.0.1", 0), ProjectApprovalSmartGitHandler)
        self.token = secrets.token_urlsafe(32)
        self.revision = "b" * 40
        self.variables = {"COCHEM_APPROVED_BASE_SHA": self.revision}
        self.variable_status = 200
        self.variable_name_changed = variable_name_changed
        self.commit_changed = commit_changed
        self.channel_changed = False
        self.worker_missing = worker_missing
        self.paths = []
        self.metadata_auth_verified = False
        self.repository = repository
        self.setup_request = None
        self.setup_revision = "a" * 40
        self.setup_workflow_available = True
        self.setup_artifact_changes = {}
        self.setup_run_changes = {}
        self.setup_access = {"source": True, "orca": True, "cfour": True}
        self.setup_digest_changed = False
        self.setup_status = 200
        self.submitted = []
        self._git_fixture = tempfile.TemporaryDirectory(prefix='project-admission-git-')
        self.store = AdmissionGitStore.create(Path(self._git_fixture.name) / 'ledger.git')
        self.gets = []
        self.git_writes = []
        self.drop_create_ack = self.drop_patch_ack = False
        self.runs = []
        self.setup_schema = 'cochem.project-setup/2'
        self.capability_changes = {}
        self.source_changes = {}
        self.admission_metadata_status = 200
        self.admission_run_changes = {}
        self.admission_project_id = 17
        self.dispatch_terminal_race = False
        self.binding_patch_race = False
        self.race_new_submission = None
        self.blocked_route = None
        self.blocked_entered, self.blocked_release = Event(), Event()
        _SMART_FIXTURES["configure_smart_git_peer"](self)


class ProjectApprovalHandler(AdmissionGitHandler):
    def log_message(self, fmt, *args):
        self.server.gets.append({"access": fmt % args})

    def do_GET(self):
        if '/git/' in self.path:
            peer = self.server
            if peer.blocked_route == self.path:
                peer.blocked_entered.set()
                if not peer.blocked_release.wait(timeout=5):
                    self.answer({'error': 'bounded engineering HTTP barrier expired'}, 503)
                    return
            return super().do_GET()
        peer = self.server
        peer.paths.append(self.path)
        if peer.blocked_route == self.path:
            peer.blocked_entered.set()
            if not peer.blocked_release.wait(timeout=5):
                self.answer({'error': 'bounded engineering HTTP barrier expired'}, 503)
                return
        if self.headers.get("Authorization") != "Bearer " + peer.token:
            self.answer({}, 401)
            return
        prefix = "/repos/" + peer.repository
        if self.path == prefix:
            self.answer({"id": peer.admission_project_id, "full_name": peer.repository, "private": True,
                         "owner": {"type": "User", "login": "student"},
                         "default_branch": "main", "permissions": {"push": True},
                         "fork": False, "archived": False, "disabled": False})
        elif self.path in {prefix + "/actions/workflows/student_research.yml", prefix + "/actions/workflows/123"}:
            self.answer({"id": 123, "state": "active", "path": ".github/workflows/student_research.yml"})
        elif self.path.startswith(prefix + '/actions/workflows/123/runs?'):
            page = int(urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)['page'][0])
            self.answer({'total_count': len(peer.runs), 'workflow_runs': peer.runs[(page-1)*100:page*100]})
        elif self.path.startswith(prefix + '/actions/runs/') and self.path.rsplit('/', 1)[-1].isdigit():
            run_id = int(self.path.rsplit('/', 1)[-1])
            matches = [run for run in peer.runs if run['id'] == run_id]
            self.answer({**matches[0], **peer.admission_run_changes} if len(matches) == 1 else {}, peer.admission_metadata_status if len(matches) == 1 else 404)
        elif self.path == prefix + "/commits/main":
            self.answer({"sha": "a" * 40})
        elif self.path == prefix + "/actions/workflows/student_project_setup.yml":
            peer.metadata_auth_verified = True
            self.answer({"id": 124, "state": "active", "path": ".github/workflows/student_project_setup.yml"},
                        peer.setup_status if peer.setup_workflow_available else 404)
        elif self.path.startswith(prefix + "/actions/workflows/124/runs?"):
            run = {"id": 456, "run_attempt": 1, "display_title": "CoChem setup " + peer.setup_request,
                   "event": "workflow_dispatch", "head_sha": peer.setup_revision,
                   "head_branch": "main", "workflow_id": 124, "status": "completed",
                   "conclusion": "success", "html_url": "https://github.com/" + peer.repository + "/actions/runs/456"}
            self.answer({"workflow_runs": [{**run, **peer.setup_run_changes}]})
        elif self.path == prefix + "/actions/runs/456/artifacts?per_page=100":
            content = self.setup_archive()
            digest = "0" * 64 if peer.setup_digest_changed else hashlib.sha256(content).hexdigest()
            self.answer({"artifacts": [{"id": 789, "name": "cochem-setup-" + peer.setup_request + "-456-1",
                         "expired": False, "size_in_bytes": len(content), "digest": "sha256:" + digest}]})
        elif self.path == prefix + "/actions/artifacts/789/zip":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(self.setup_archive())
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
        elif (self.path.startswith('/repos/ProfJJK-CoChem/CoChem-BASE/contents/')
              or self.path.startswith(prefix + '/contents/')):
            parsed = urllib.parse.urlsplit(self.path)
            relative = urllib.parse.unquote(parsed.path.split('/contents/', 1)[1])
            revision = urllib.parse.parse_qs(parsed.query).get('ref', [''])[0]
            source = Path(__file__).resolve().parents[2]
            allowed = admission_contract.REQUIRED_PATHS | {admission_contract.DESCRIPTOR_PATH}
            if relative not in allowed or revision not in {peer.revision, peer.setup_revision} or peer.worker_missing:
                self.answer({}, 404)
            else:
                raw = peer.source_changes.get((revision, relative), (source / relative).read_bytes())
                self.answer({'type': 'file', 'path': relative, 'encoding': 'base64', 'size': len(raw),
                    'sha': admission_contract.blob_id(raw), 'content': base64.b64encode(raw).decode()})
        else:
            self.answer({"message": "Unexpected engineering endpoint"}, 404)

    def answer(self, payload, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(canonical_json(payload))

    def do_POST(self):
        if '/git/' in self.path:
            return super().do_POST()
        peer = self.server
        peer.paths.append(self.path)
        if self.headers.get("Authorization") != "Bearer " + peer.token:
            self.answer({}, 401)
            return
        if self.path == "/repos/" + peer.repository + "/actions/workflows/123/dispatches":
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            submitted = decode_request(data["inputs"]["request_base64"], data["inputs"]["request_sha256"])
            peer.submitted.append(submitted)
            if submitted['capability_probe'] is None:
                assert set(data['inputs']) == {'request_id', 'request_sha256', 'request_base64', 'admission_anchor'}
                assert admission_contract.HEX40.fullmatch(data['inputs']['admission_anchor'])
            else:
                assert set(data['inputs']) == {'request_id', 'request_sha256', 'request_base64'}
            number = 458 + len(peer.submitted)
            peer.runs.append({'id': number, 'run_attempt': 1, 'workflow_id': 123,
                'repository': {'id': 17, 'full_name': peer.repository}, 'event': 'workflow_dispatch',
                'display_title': 'CoChem student ' + submitted['request_id'], 'head_branch': data['ref'],
                'head_sha': submitted['source_sha'], 'status': 'queued', 'conclusion': None,
                'html_url': f'https://github.com/{peer.repository}/actions/runs/{number}'})
            if peer.dispatch_terminal_race:
                peer.dispatch_terminal_race = False
                self._advance_old_request_for_race()
            self.answer({}, 204)
            return
        if self.path != "/repos/" + peer.repository + "/actions/workflows/124/dispatches":
            self.answer({}, 404)
            return
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert data["ref"] == "main"
        peer.setup_request = data["inputs"]["request_id"]
        assert str(uuid.UUID(peer.setup_request)) == peer.setup_request
        self.answer({}, 204)

    def _advance_old_request_for_race(self):
        """Actual local Git append + nested HTTP at a response boundary, no chemistry."""
        from cochem_base.interfaces import student_actions_admission_git as transport
        peer = self.server
        observer = StudentActionsClient(peer.repository, branch='main', token=peer.token,
            api_url=f'http://127.0.0.1:{peer.server_port}', allow_loopback=True)
        actual = transport.ActionsAdmissionTransport(observer)
        old = peer.store.read()
        bound = peer.store.bind(actual, admission_contract.identity(old))
        run = next(run for run in peer.runs if run['id'] == bound.binding['run_id'])
        # An API-shaped failure is only an engineering transport observation; no
        # result/output/operation_performed success is created by this fixture.
        run.update(status='completed', conclusion='failure')
        peer.store.finish(actual, admission_contract.identity(bound))
        replacement = json.loads(bound.raw)
        replacement['request_id'] = 'ac72d7ea-3c83-425e-9163-e5d5b15d0af2'
        new = peer.store.prepare(canonical_json(replacement), repository_id=17, branch='main', workflow_id=123)
        peer.race_new_submission = observer._saved_admission(new)

    def _patch_body(self, body):
        peer = self.server
        if peer.binding_patch_race:
            files, unused_parent = peer.store.files(body['sha'])
            state = admission_contract.strict(files['state.json'])
            if state['phase'] == 'bound':
                peer.binding_patch_race = False
                self._advance_old_request_for_race()
                peer.git_writes.append({'method': 'PATCH', 'path': self.path, 'body': body, 'refused_after_competing_append': True})
                self.answer({'error': 'actual competing local Git append won'}, 422)
                return
        return super()._patch_body(body)

    def setup_archive(self):
        peer = self.server
        metadata = {"schema_version": peer.setup_schema, "request_id": peer.setup_request,
                    "repository": peer.repository, "source_sha": peer.setup_revision,
                    "run_id": 456, "run_attempt": 1,
                    "approved_base_sha": peer.variables.get("COCHEM_APPROVED_BASE_SHA", ""),
                    "course_channel": peer.variables.get("COCHEM_COURSE_CHANNEL", ""),
                    "access": peer.setup_access}
        if peer.setup_schema == 'cochem.project-setup/2':
            raw = (Path(__file__).resolve().parents[2] / admission_contract.DESCRIPTOR_PATH).read_bytes()
            metadata['research_admission'] = {'protocol': admission_contract.PROTOCOL,
                'ledger_ref': admission_contract.LEDGER_REF, 'descriptor_sha256': hashlib.sha256(raw).hexdigest(),
                **peer.capability_changes}
        metadata.update(peer.setup_artifact_changes)
        if peer.variable_name_changed:
            metadata["unexpected_field"] = "not part of the version contract"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
            info = zipfile.ZipInfo("project-setup.json", date_time=(2026, 1, 1, 0, 0, 0))
            archive.writestr(info, canonical_json(metadata))
        return buffer.getvalue()


class ProjectApprovalSmartGitHandler(_SMART_FIXTURES['SmartGitHTTPMixin'], ProjectApprovalHandler):
    """Serve the original real bare fixture through actual Git smart HTTP."""
    protocol_version = 'HTTP/1.0'


def finish_smart_git_peer(peer):
    """Reap only fixture-owned CGI children and finish its actual handler threads."""
    peer.git_release.set()
    for handler in peer.git_handlers:
        handler.join(timeout=5)
        assert not handler.is_alive()
    for child in peer.cgi_children:
        if child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                # The owned group may have naturally completed before cleanup.
                assert child.poll() is not None
        child.wait(timeout=2)
        assert child.returncode is not None


@pytest.fixture
def project_approval_peer(request):
    configuration = request.param if hasattr(request, "param") else {}
    peer = ProjectApprovalServer(**configuration)
    thread = Thread(target=peer.serve_forever, daemon=True)
    thread.start()
    try:
        yield peer
    finally:
        peer.git_release.set()
        peer.shutdown()
        peer.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
        finish_smart_git_peer(peer)
        peer._git_fixture.cleanup()


def project_approval_client(peer, tmp_path):
    return StudentActionsClient(peer.repository, token=peer.token, repository_root=tmp_path / "source",
                                artifact_dir=tmp_path / "runtime",
                                api_url=f"http://127.0.0.1:{peer.server_port}", allow_loopback=True)


def test_codespace_can_check_setup_without_variables_read_permission(project_approval_peer, tmp_path):
    peer = project_approval_peer
    peer.variable_status = 403
    selected = project_approval_client(peer, tmp_path).preflight()
    assert selected["worker_source_sha"] == peer.revision
    assert selected["project_access"] == {"source": True, "orca": True, "cfour": True}
    assert selected["setup_check_url"] == "https://github.com/student/project/actions/runs/456"
    assert not any("/actions/variables/" in path or "/secrets/" in path for path in peer.paths)


@pytest.mark.parametrize("project_approval_peer", [{"repository": "ProfJJK-CoChem/CoChem-BASE"}], indirect=True)
def test_instructor_canonical_codespace_checks_setup_with_actions_access(project_approval_peer, tmp_path):
    peer = project_approval_peer
    peer.variable_status = 403
    selected = project_approval_client(peer, tmp_path).preflight()
    assert selected["repository"] == "ProfJJK-CoChem/CoChem-BASE"
    assert selected["worker_source_sha"] == peer.revision
    assert peer.metadata_auth_verified
    assert not any("/actions/variables/" in path for path in peer.paths)


@pytest.mark.parametrize("changes", [
    {"request_id": "71134ed2-5204-4756-8cf8-1b12be69474e"},
    {"repository": "someone/else"}, {"source_sha": "c" * 40},
    {"run_id": 457}, {"run_attempt": 2}, {"run_attempt": True},
    {"access": {"source": "true", "orca": True, "cfour": True}},
    {"access": {"source": True, "orca": True}}, {"unexpected_field": "rejected"},
])
def test_setup_result_must_match_original_project_and_run(project_approval_peer, tmp_path, changes):
    peer = project_approval_peer
    peer.setup_artifact_changes = changes
    with pytest.raises(StudentActionsError, match="setup-check result"):
        project_approval_client(peer, tmp_path).preflight()
    assert not peer.submitted
    assert not any("/repos/ProfJJK-CoChem/CoChem-BASE/" in path for path in peer.paths)


@pytest.mark.parametrize("changes", [{"head_sha": "c" * 40}, {"workflow_id": 999},
                                     {"event": "push"}, {"head_branch": "other"}])
def test_changed_setup_run_is_rejected_before_artifact_download(project_approval_peer, tmp_path, changes):
    peer = project_approval_peer
    peer.setup_run_changes = changes
    with pytest.raises(StudentActionsError, match="project changed"):
        project_approval_client(peer, tmp_path).preflight()
    assert not any("/artifacts" in path for path in peer.paths)
    assert not peer.submitted


def test_setup_artifact_digest_mismatch_prevents_calculation(project_approval_peer, tmp_path):
    peer = project_approval_peer
    peer.setup_digest_changed = True
    with pytest.raises(StudentActionsError, match="integrity check"):
        project_approval_client(peer, tmp_path).preflight()
    assert not peer.submitted


def test_old_project_missing_setup_workflow_has_an_actionable_update_link(project_approval_peer, tmp_path):
    peer = project_approval_peer
    peer.setup_workflow_available = False
    with pytest.raises(StudentActionsError, match="workflow files in this project's repository") as refused:
        project_approval_client(peer, tmp_path).preflight()
    assert refused.value.setup_url == "https://github.com/ProfJJK-CoChem/CoChem-BASE#readme"
    assert not peer.submitted


@pytest.mark.parametrize('changes', [None, {'protocol': 'unknown'}, {'descriptor_sha256': '0'*64}])
def test_old_or_mismatched_capability_refuses_before_claim_or_science_dispatch(project_approval_peer, tmp_path, changes):
    peer = project_approval_peer
    if changes is None:
        peer.setup_schema = 'cochem.project-setup/1'
    else:
        peer.capability_changes = changes
    with pytest.raises(StudentActionsError):
        project_approval_client(peer, tmp_path).submit(_request()['calculation'])
    assert not peer.submitted and not peer.git_writes
    assert peer.store.tip() is None


@pytest.mark.parametrize('revision', ['assignment', 'worker'])
def test_every_advertised_protected_file_is_compared_at_both_sources(project_approval_peer, tmp_path, revision):
    peer = project_approval_peer
    sha = peer.setup_revision if revision == 'assignment' else peer.revision
    for relative in admission_contract.REQUIRED_PATHS:
        peer.source_changes = {(sha, relative): b'Changed engineering source bytes; not application execution'}
        with pytest.raises(StudentActionsError):
            project_approval_client(peer, tmp_path).submit(_request()['calculation'])
        assert not peer.submitted and not peer.git_writes and peer.store.tip() is None


def test_free_base_calculation_submits_without_any_private_component_access(project_approval_peer, tmp_path):
    peer = project_approval_peer
    peer.setup_access = {"source": False, "orca": False, "cfour": False}
    submitted = project_approval_client(peer, tmp_path).submit(_request()["calculation"])
    assert submitted["status"] == "queued"
    assert len(peer.submitted) == 1
    assert peer.submitted[0]["calculation"]["engine"] == "xtb"
    assert peer.submitted[0]["worker_source_sha"] == peer.revision
    assert peer.submitted[0]["source_sha"] == peer.setup_revision
    assert peer.token not in json.dumps(peer.submitted)


@pytest.mark.parametrize("engine", ["orca", "cfour"])
def test_available_licensed_engine_is_independent_of_other_optional_components(project_approval_peer, tmp_path, engine):
    peer = project_approval_peer
    peer.setup_access = {"source": False, "orca": engine == "orca", "cfour": engine == "cfour"}
    calculation = {**_request()["calculation"], "engine": engine, "method": "HF", "basis_set": "STO-3G"}
    submitted = project_approval_client(peer, tmp_path).submit(calculation)
    assert submitted["status"] == "queued"
    assert len(peer.submitted) == 1
    assert peer.submitted[0]["calculation"] == calculation


@pytest.mark.parametrize("module", ["topos", "torq"])
def test_public_provider_submits_without_private_source_credentials(project_approval_peer, tmp_path, module):
    peer = project_approval_peer
    peer.setup_access = {"source": False, "orca": False, "cfour": False}
    geometry = _request()["calculation"]["geometry"]
    provider = {"schema_version": "cochem.student-provider/1", "module": module,
                "operation": "geometry_analysis", "artifact": "inputs/water.xyz",
                "artifact_sha256": hashlib.sha256(geometry.encode()).hexdigest(), "options": {}}
    submitted = project_approval_client(peer, tmp_path).submit(
        None, provider=provider, xyz_files={provider["artifact"]: geometry})
    assert submitted["status"] == "queued"
    assert len(peer.submitted) == 1
    assert peer.submitted[0]["provider"] == provider
    assert peer.submitted[0]["worker_source_sha"] == peer.revision
    assert peer.submitted[0]["files"][provider["artifact"]]["sha256"] == provider["artifact_sha256"]
    assert peer.token not in json.dumps(peer.submitted)


def test_public_provider_still_requires_its_selected_licensed_engine(project_approval_peer, tmp_path):
    from cochem_base.interfaces.student_research import build_topos_request

    peer = project_approval_peer
    peer.setup_access = {"source": False, "orca": False, "cfour": False}
    geometry = _request()["calculation"]["geometry"]
    provider = {"schema_version": "cochem.student-provider/1", "module": "topos",
                "operation": "energy", "artifact": "inputs/water.xyz",
                "artifact_sha256": hashlib.sha256(geometry.encode()).hexdigest(),
                "options": {"topos_request": build_topos_request(
                    geometry, operation="energy", charge=0, multiplicity=1,
                    engine="orca", method="HF", options={"basis": "STO-3G"})}}
    with pytest.raises(StudentActionsError, match="ORCA access") as refused:
        project_approval_client(peer, tmp_path).submit(
            None, provider=provider, xyz_files={provider["artifact"]: geometry})
    assert refused.value.setup_url.endswith("/actions/runs/456")
    assert not peer.submitted
    assert not any("/git/" in path for path in peer.paths)


def test_setup_report_producer_emits_only_nonsecret_status_from_actual_process(tmp_path):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "project-setup.json"
    env = {**os.environ, "SETUP_REQUEST_ID": str(uuid.uuid4()), "GITHUB_REPOSITORY": "student/project",
           "GITHUB_SHA": "a" * 40, "GITHUB_EVENT_NAME": "workflow_dispatch", "DEFAULT_BRANCH": "main",
           "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ID": "456", "GITHUB_RUN_ATTEMPT": "1",
           "COCHEM_APPROVED_BASE_SHA": "b" * 40, "COCHEM_COURSE_CHANNEL": "",
           "COCHEM_SOURCE_AVAILABLE": "false", "COCHEM_ORCA_AVAILABLE": "true",
           "COCHEM_CFOUR_AVAILABLE": "false", "UNRELATED_PRIVATE_VALUE": secrets.token_hex(32)}
    executed = subprocess.run([sys.executable, "-B", "-I", "-S",
        str(root / "scripts/check_student_project_setup.py"), "--output", str(output)],
        env=env, text=True, capture_output=True, timeout=15, check=False)
    assert executed.returncode == 0, executed.stderr
    metadata = json.loads(output.read_bytes())
    assert metadata["access"] == {"source": False, "orca": True, "cfour": False}
    assert metadata["approved_base_sha"] == "b" * 40
    assert metadata["request_id"] == env["SETUP_REQUEST_ID"]
    assert env["UNRELATED_PRIVATE_VALUE"] not in output.read_text() + executed.stdout + executed.stderr
    # The producer refuses a branch change and creates no second report.
    env["GITHUB_REF"] = "refs/heads/other"
    refused_output = tmp_path / "refused.json"
    refused = subprocess.run([sys.executable, "-B", "-I", "-S",
        str(root / "scripts/check_student_project_setup.py"), "--output", str(refused_output)],
        env=env, text=True, capture_output=True, timeout=15, check=False)
    assert refused.returncode != 0
    assert not refused_output.exists()


@pytest.mark.parametrize("credential_kind", ["public-job", "invalid-optional-source", "approval-changed"])
def test_worker_public_source_access_preserves_server_version_guard(project_approval_peer, tmp_path, credential_kind):
    """Real HTTP + isolated Python prove authorization, without running chemistry."""
    peer = project_approval_peer
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "worker"
    output.mkdir()
    request = _request()
    request["worker_source_sha"] = peer.revision
    encoded, digest = encode_request(request)
    (output / "request.json").write_bytes(canonical_json(request))
    optional_source = secrets.token_urlsafe(32) if credential_kind == "invalid-optional-source" else ""
    env = {**os.environ, "COCHEM_SOURCE_CREDENTIAL": optional_source,
           "GITHUB_TOKEN": peer.token,
           "COCHEM_APPROVED_BASE_SHA": "c" * 40 if credential_kind == "approval-changed" else peer.revision,
           "COCHEM_COURSE_CHANNEL": "", "REQUEST_BASE64": encoded, "REQUEST_SHA256": digest}
    code = ("import runpy,sys; from pathlib import Path; "
            "module=runpy.run_path(sys.argv[1]); "
            "module['approve_worker'](Path(sys.argv[2]),api_url=sys.argv[3],allow_loopback=True)")
    executed = subprocess.run([sys.executable, "-B", "-I", "-S", "-c", code,
        str(root / "scripts/run_student_research.py"), str(output), f"http://127.0.0.1:{peer.server_port}"],
        env=env, capture_output=True, text=True, timeout=15, check=False)
    assert peer.token not in executed.stdout + executed.stderr
    if optional_source:
        assert optional_source not in executed.stdout + executed.stderr
    if credential_kind == "approval-changed":
        assert executed.returncode != 0
        assert "not authorized" in executed.stderr
        assert not (output / "worker-approval.json").exists()
        assert not peer.paths
    else:
        assert executed.returncode == 0, executed.stderr
        result = json.loads((output / "worker-approval.json").read_bytes())
        assert result["worker_source_sha"] == peer.revision
        assert result["assignment_source_sha"] == request["source_sha"]
        assert result["approval"] == "instructor-actions-variable"
        assert peer.paths == ["/repos/ProfJJK-CoChem/CoChem-BASE/commits/" + peer.revision]


def test_project_setup_workflow_receives_only_presence_booleans_and_job_identity():
    import yaml

    root = Path(__file__).resolve().parents[2]
    workflow = yaml.safe_load((root / ".github/workflows/student_project_setup.yml").read_text())
    assert workflow["permissions"] == {"contents": "read"}
    steps = workflow["jobs"]["setup"]["steps"]
    producer = next(step for step in steps if "check_student_project_setup.py" in step.get("run", ""))
    for kind in ("SOURCE", "ORCA", "CFOUR"):
        assert producer["env"]["COCHEM_" + kind + "_AVAILABLE"] == (
            "${{ secrets[vars.COCHEM_" + kind + "_ACCESS_SECRET] != '' }}")
    assert not any("TOKEN" in name or "CREDENTIAL" in name for name in producer["env"])
    worker = yaml.safe_load((root / ".github/workflows/student_research.yml").read_text())
    steps = worker["jobs"]["research"]["steps"]
    approval = next(step for step in steps if "--approve-worker-only" in step.get("run", ""))
    assert approval["env"]["GITHUB_TOKEN"] == "${{ github.token }}"
    assert "COCHEM_SOURCE_CREDENTIAL" not in approval["env"]
    source = next(step for step in steps if step.get("with", {}).get("path") == "worker")
    assert source["with"]["token"] == "${{ github.token }}"
    execution = next(step for step in steps if step.get("name") == "Run the requested native calculation or reviewed scientific provider")
    assert "env" not in execution


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
def test_setup_workflow_denial_never_falls_back_to_main(project_approval_peer, tmp_path, status):
    peer = project_approval_peer
    peer.setup_status = status
    with pytest.raises(StudentActionsError) as refused:
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


@pytest.mark.parametrize("project_approval_peer", [{"variable_name_changed": True},
                                                   {"commit_changed": True},
                                                   {"worker_missing": True}], indirect=True)
def test_changed_target_approval_or_missing_exact_worker_refuses(project_approval_peer, tmp_path):
    peer = project_approval_peer
    with pytest.raises(StudentActionsError):
        project_approval_client(peer, tmp_path).preflight()
    assert not any(path.endswith("/commits/main") and "CoChem-BASE" in path for path in peer.paths)


@pytest.mark.parametrize("channel", ["main", "../escape.json", ".cochem/course-channels/research.json?ref=evil"])
def test_project_course_channel_is_data_only(project_approval_peer, tmp_path, channel):
    peer = project_approval_peer
    peer.variables = {"COCHEM_COURSE_CHANNEL": channel}
    with pytest.raises(StudentActionsError, match="BASE version file"):
        project_approval_client(peer, tmp_path).preflight()
    assert not any("/repos/ProfJJK-CoChem/CoChem-BASE/" in path for path in peer.paths)


def test_project_channel_invalid_revision_refuses_without_latest_fallback(project_approval_peer, tmp_path):
    peer = project_approval_peer
    peer.variables = {"COCHEM_COURSE_CHANNEL": ".cochem/course-channels/research.json"}
    peer.channel_changed = True
    with pytest.raises(StudentActionsError, match="exact BASE version"):
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


def test_worker_seals_nested_native_manifest_and_rejects_later_tampering(tmp_path):
    """Exercise the real finalizer and importer with filesystem-only evidence."""
    from scripts.run_student_research import finalize

    contents, submission = _archive(_request())
    evidence = tmp_path / "worker-evidence"
    evidence.mkdir()
    with zipfile.ZipFile(io.BytesIO(contents)) as archive:
        archive.extractall(evidence)
    native_manifest = evidence / "native/publication-manifest.json"
    native_manifest.parent.mkdir()
    original = canonical_json({"schema_version": "cochem.actions-publication/1",
                               "files": {}, "scientific_execution_performed": False})
    native_manifest.write_bytes(original)

    manifest = finalize(evidence)
    assert manifest["files"]["native/publication-manifest.json"] == {
        "sha256": hashlib.sha256(original).hexdigest(), "size_bytes": len(original)}
    assert "publication-manifest.json" not in manifest["files"]
    assert finalize(evidence) == manifest

    sealed = io.BytesIO()
    with zipfile.ZipFile(sealed, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(evidence.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(evidence).as_posix())
    destination = tmp_path / "results"
    result = _extract_verified_archive(sealed.getvalue(), destination, submission, submission)
    assert result["report"]["operation_performed"] is False
    assert (destination / "native/publication-manifest.json").read_bytes() == original
    (destination / "native/publication-manifest.json").write_bytes(original + b" ")
    with pytest.raises(StudentActionsError, match="integrity failed: native/publication-manifest.json"):
        verify_retained_results(destination, submission)


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


def _student_admission_workflow():
    import yaml

    return yaml.safe_load((Path(__file__).resolve().parents[2]
                           / '.github/workflows/student_research.yml').read_text())


def test_student_admission_preserves_transport_and_presecret_authority():
    workflow = _student_admission_workflow()
    dispatch = workflow.get('on', workflow.get(True))['workflow_dispatch']
    assert set(dispatch['inputs']) == {'request_id', 'request_sha256', 'request_base64', 'admission_anchor'}
    assert dispatch['inputs']['admission_anchor'] == {'description': 'BASE-generated exact saved research dispatch commit (empty for a probe)', 'required': False, 'default': '', 'type': 'string'}
    assert workflow['permissions'] == {'contents': 'read'} and 'concurrency' not in workflow
    admission, research = workflow['jobs']['admission'], workflow['jobs']['research']
    assert 'concurrency' not in admission and admission['timeout-minutes'] == 5
    assert admission['permissions'] == research['permissions'] == {'contents': 'read', 'actions': 'read'}
    assert admission['outputs'] == {'probe': '${{ steps.route.outputs.probe }}'}
    steps = admission['steps']
    names = {step.get('name'): index for index, step in enumerate(steps)}
    ordered = ['Verify submitted structures, identity and finite resource limits',
               'Verify the instructor-approved canonical worker revision',
               'Obtain the exact canonical BASE worker without changing student files',
               'Audit the approved BASE source before application imports',
               'Revalidate scientific capabilities and resources in the approved worker',
               'Recheck the current private project before provisioning access',
               'Verify this exact admitted run before publishing the route',
               'Publish the canonical admitted request route']
    assert [names[name] for name in ordered] == sorted(names[name] for name in ordered)
    assert len(steps) == 13
    for step in steps:
        assert 'secrets[' not in json.dumps(step)
        assert not step.get('uses', '').startswith('./worker/')
        assert '--capability-probe' not in step.get('run', '')
        assert 'sudo ' not in step.get('run', '')
        assert 'hosted_dashboard.py setup' not in step.get('run', '')
    route = next(step for step in steps if step.get('id') == 'route')
    assert route['env'] == {'VERIFIED_PROBE': '${{ steps.worker.outputs.probe }}'}
    assert research['needs'] == 'admission'
    assert research['concurrency'] == {
        'group': "${{ needs.admission.outputs.probe == 'true' && format('cochem-student-probe-{0}', github.repository) || format('cochem-student-research-{0}', github.repository) }}",
        'cancel-in-progress': False}
    assert "needs.admission.result == 'success'" in research['if']
    assert "(needs.admission.outputs.probe == 'true' || needs.admission.outputs.probe == 'false')" in research['if']
    failure = next(step for step in steps if step.get('id') == 'failure_publication')
    upload = next(step for step in steps if step.get('uses', '').startswith('actions/upload-artifact@'))
    assert failure['if'] == "always() && steps.request.outcome == 'success' && steps.route.outcome != 'success'"
    assert upload['if'] == failure['if'] + " && steps.failure_publication.outcome == 'success'"
    science_upload = next(step for step in research['steps']
                          if step.get('uses', '').startswith('actions/upload-artifact@'))
    assert upload['with']['name'] == science_upload['with']['name'] == (
        'cochem-student-${{ inputs.request_id }}-${{ github.run_id }}-${{ github.run_attempt }}')
    assert upload['with']['if-no-files-found'] == 'error'


def test_all_three_readonly_barriers_skip_only_canonical_probe_and_keep_legacy_probe_route():
    """Actual source/workflow contract; route-shell negatives remain separate.

    This does not execute GitHub expression evaluation or a hosted job. It proves
    the exact guards use the prior canonical classification, not request input.
    """
    workflow = _student_admission_workflow()
    barriers = [step for job in ('admission', 'research')
        for step in workflow['jobs'][job]['steps']
        if '--verify-admission-only' in step.get('run', '')]
    assert len(barriers) == 3
    for step in barriers:
        assert step['if'] == "steps.worker.outputs.probe != 'true'"
        assert step['env'] == {'GITHUB_TOKEN': '${{ github.token }}'}
    # Preserve the exact approved historical worker as a compatibility fixture.
    # No old application is imported/executed; no source guard is changed.
    root = Path(__file__).resolve().parents[2]
    legacy = subprocess.run(['git', '-C', str(root), 'show',
        '388088281b8c23951f191edb88f3e865eaa8146d:scripts/run_student_research.py'],
        capture_output=True, timeout=10, check=True).stdout
    assert b'--verify-admission-only' not in legacy
    assert b'--verify-worker-only' in legacy and b'capability_probe' in legacy
    route = next(step for step in workflow['jobs']['admission']['steps'] if step.get('id') == 'route')
    assert route['env'] == {'VERIFIED_PROBE': '${{ steps.worker.outputs.probe }}'}
    assert "(needs.admission.outputs.probe == 'true' || needs.admission.outputs.probe == 'false')" in workflow['jobs']['research']['if']


@pytest.mark.parametrize('value', ['true', 'false', '', 'TRUE', 'true\nprobe=false', '$(touch marker)'])
def test_admission_route_publication_shell(tmp_path, value):
    script = next(step['run'] for step in _student_admission_workflow()['jobs']['admission']['steps']
                  if step.get('id') == 'route')
    output = tmp_path / 'github-output'
    result = subprocess.run(['bash', '-e', '-c', script], cwd=tmp_path,
        env=dict(os.environ, VERIFIED_PROBE=value, GITHUB_OUTPUT=str(output)),
        capture_output=True, text=True, timeout=10)
    accepted = value in {'true', 'false'}
    assert (result.returncode == 0) is accepted, result.stdout + result.stderr
    if accepted:
        assert output.read_bytes() == f'probe={value}\n'.encode()
    else:
        assert not output.exists()
    assert not (tmp_path / 'marker').exists()


@pytest.mark.parametrize(('admitted', 'verified'), [
    ('true', 'true'), ('false', 'false'), ('true', 'false'), ('false', 'true'),
    ('', 'false'), ('false', ''), ('TRUE', 'TRUE'), ('true\n', 'true\n'),
    ('$(touch marker)', '$(touch marker)'),
])
def test_research_admitted_route_equality_shell(tmp_path, admitted, verified):
    script = next(step['run'] for step in _student_admission_workflow()['jobs']['research']['steps']
                  if step.get('name') == 'Bind the canonical worker route to the admitted request')
    result = subprocess.run(['bash', '-e', '-c', script], cwd=tmp_path,
        env=dict(os.environ, ADMITTED_PROBE=admitted, VERIFIED_PROBE=verified),
        capture_output=True, text=True, timeout=10)
    assert (result.returncode == 0) is (admitted == verified and admitted in {'true', 'false'})
    assert not (tmp_path / 'marker').exists()


_STUDENT_ADMISSION_CHILD = r'''
import hashlib, io, json, os, runpy, sys, zipfile
from pathlib import Path
root, workspace, api_url, mode, case, program_path = sys.argv[1:]
root, workspace = Path(root), Path(workspace)
if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
    startup = sys.modules.get('sitecustomize')
    assert startup is not None
    assert Path(startup.__file__).resolve() == root / 'ci_tools/quarantine_startup/sitecustomize.py'
    state = getattr(sys.modules.get('ci_tools.source_quarantine'), '_active', None)
    assert state is not None and state['copied'] == root
module = runpy.run_path(str(root / 'scripts/run_student_research.py'))
output = Path(os.environ['RUNNER_TEMP']) / 'cochem-student-evidence'
def no_probe_output():
    path = Path(os.environ['GITHUB_OUTPUT'])
    assert not path.exists() or not any(line.startswith('probe=') for line in path.read_text().splitlines())
if mode == 'canonical':
    try:
        request = module['preflight'](output)
        if case == 'changed_saved_request':
            changed = dict(request, submitted_at='2026-10-09T00:00:00+00:00')
            (output / 'request.json').write_bytes(module['contract'].canonical_json(changed))
        module['approve_worker'](output, api_url=api_url, allow_loopback=True)
        module['verify_worker_checkout'](output)
    except ValueError:
        assert case != 'valid'
        no_probe_output()
        if case in {'digest', 'resource_allocation', 'assignment_source', 'default_branch'}:
            assert not output.exists()
        else:
            assert (output / 'student-result.json').exists()
    else:
        assert case == 'valid'
        probe = request['capability_probe'] is not None
        lines = Path(os.environ['GITHUB_OUTPUT']).read_text().splitlines()
        assert lines.count('probe=' + str(probe).lower()) == 1
        approval = module['contract'].strict_json((output / 'worker-approval.json').read_bytes())
        source = module['contract'].strict_json((output / 'worker-source.json').read_bytes())
        assert approval['worker_source_sha'] == source['worker_source_sha'] == request['worker_source_sha']
        assert approval['assignment_source_sha'] == request['source_sha']
        catalog = (output / 'worker-module-distribution.json').read_bytes()
        assert source['module_manifest_sha256'] == hashlib.sha256(catalog).hexdigest()
        report = module['contract'].strict_json((output / 'student-result.json').read_bytes())
        assert report['status'] == 'prepared' and report['operation_performed'] is False
    print('admission-control-passed')
else:
    request = module['preflight'](output)
    try:
        module['approve_worker'](output, api_url=api_url, allow_loopback=True)
    except ValueError as error:
        assert 'exact approved worker source' in str(error)
    else:
        raise AssertionError('The real wrong-commit approval response unexpectedly succeeded')
    path = output / 'student-result.json'
    report = module['contract'].strict_json(path.read_bytes())
    assert report['status'] == 'prepared' and report['operation_performed'] is False
    field_faults = {'completed': ('status', 'completed'), 'operation_true': ('operation_performed', True),
        'operation_zero': ('operation_performed', 0), 'probe_performed': ('capability_probe_performed', True),
        'wrong_request': ('request_id', 'e5b58d6d-f042-4ffb-91df-e2092bf8d311'),
        'wrong_repository': ('repository', 'different/project'), 'wrong_source': ('source_sha', '0' * 40),
        'wrong_worker': ('worker_source_sha', '0' * 40), 'wrong_digest': ('payload_sha256', '0' * 64),
        'wrong_run': ('run_id', 2), 'wrong_attempt': ('run_attempt', 2),
        'boolean_run': ('run_id', True), 'boolean_attempt': ('run_attempt', True)}
    if case in field_faults:
        field, value = field_faults[case]
        report[field] = value
    if case == 'changed_saved_request':
        changed = dict(request, repository='different/project')
        (output / 'request.json').write_bytes(module['contract'].canonical_json(changed))
    elif case in {'saved_cores_float', 'saved_memory_float'}:
        changed = dict(request, resources=dict(request['resources']))
        field = 'cores' if case == 'saved_cores_float' else 'maxcore_mb'
        changed['resources'][field] = float(changed['resources'][field])
        assert changed == request  # Numeric equality must not become byte identity.
        assert module['contract'].canonical_json(changed) != module['contract'].canonical_json(request)
        (output / 'request.json').write_bytes(module['contract'].canonical_json(changed))
    path.write_bytes(module['contract'].canonical_json(report))
    if case == 'oversize_report':
        path.write_bytes(b' ' * (4 * 1024 * 1024 + 1))
    before = path.read_bytes()
    injected = {'done': False}
    if case.startswith('post_manifest_'):
        def corrupt_actual_manifest(event, arguments):
            if event != 'open' or injected['done']:
                return
            try:
                target = Path(os.fsdecode(arguments[0]))
            except (TypeError, ValueError):
                return
            if target == output / 'publication-manifest.json' and target.exists():
                injected['done'] = True
                manifest = module['contract'].strict_json(target.read_bytes())
                if case == 'post_manifest_boolean':
                    manifest['run_attempt'] = True
                elif case == 'post_manifest_identity':
                    manifest['run_id'] = 2
                if case == 'post_manifest_oversize':
                    target.write_bytes(b' ' * (4 * 1024 * 1024 + 1))
                else:
                    target.write_bytes(module['contract'].canonical_json(manifest))
        # Explicit child-only corruption at real finalizer I/O; parsing and
        # finalization remain real. This is never installed in a shared process.
        sys.addaudithook(corrupt_actual_manifest)
    try:
        exec(compile(Path(program_path).read_text(), 'tracked-admission-failure-publication', 'exec'), {})
    except ValueError:
        assert case != 'valid_failure'
        if case.startswith('post_manifest_'):
            assert injected['done'] and (output / 'publication-manifest.json').exists()
            final = module['contract'].strict_json(path.read_bytes())
            assert final['status'] == 'failed' and final['operation_performed'] is False
        else:
            assert path.read_bytes() == before
            assert not (output / 'publication-manifest.json').exists()
    else:
        assert case == 'valid_failure', 'Admission guard accepted corrupt prepared state: ' + case
        final = module['contract'].strict_json(path.read_bytes())
        assert final['status'] == 'failed' and final['operation_performed'] is False
        from cochem_base.interfaces.student_actions import StudentActionsError, _extract_verified_archive
        identity = {key: final[key] for key in ('request_id', 'repository', 'source_sha', 'worker_source_sha',
                    'payload_sha256', 'run_id', 'run_attempt')}
        submission = dict(identity, workflow_id=123, branch='main')
        def archive_bytes():
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
                for member in sorted(output.rglob('*')):
                    if member.is_file(): archive.write(member, member.relative_to(output).as_posix())
            return buffer.getvalue()
        sealed = archive_bytes()
        imported = _extract_verified_archive(sealed, workspace / 'retrieved', submission, submission)
        assert imported['report']['status'] == 'failed' and imported['report']['operation_performed'] is False
        try:
            _extract_verified_archive(sealed, workspace / 'wrong-attempt', submission,
                                      dict(submission, run_attempt=2))
        except StudentActionsError:
            pass
        else:
            raise AssertionError('A different run attempt admitted the failure archive')
        path.write_bytes(path.read_bytes() + b' ')
        try:
            _extract_verified_archive(archive_bytes(), workspace / 'changed-report', submission, submission)
        except StudentActionsError:
            pass
        else:
            raise AssertionError('Changed report bytes admitted the failure archive')
    no_probe_output()
    print('admission-control-passed')
'''


def _run_student_admission_child(peer, tmp_path, *, route='calculation', case='valid', mode='canonical'):
    from ci_tools.source_quarantine import source_paths

    root = Path(__file__).resolve().parents[2]
    revision = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    peer.revision = 'b' * 40 if case == 'wrong_checkout' else revision
    peer.commit_changed = mode == 'failure' or case == 'wrong_metadata'
    request = _request()
    request['worker_source_sha'] = peer.revision
    if route in {'provider', 'provider_resources'}:
        raw = request['calculation']['geometry'].encode()
        digest = hashlib.sha256(raw).hexdigest()
        request['calculation'] = None
        request['provider'] = {'schema_version': 'cochem.student-provider/1', 'module': 'torq',
            'operation': 'geometry_analysis', 'artifact': 'inputs/structure.xyz',
            'artifact_sha256': digest, 'options': {}}
        request['files'] = {'inputs/structure.xyz': {'content_base64': base64.b64encode(raw).decode(),
                            'sha256': digest, 'size_bytes': len(raw)}}
        if route == 'provider_resources':
            request['resources'] = {'cores': 1, 'maxcore_mb': 128}
            request['provider'].update(operation='nbo_analysis', options={
                'engine': 'orca', 'method': {'name': 'HF', 'basis': 'STO-3G'},
                'charge': 0, 'multiplicity': 1, 'cores': 2, 'memory_mb': 1024})
    elif route == 'capability_probe':
        request.update(calculation=None, capability_probe={'engines': ['orca', 'cfour']})
    if case == 'dual_route':
        request['capability_probe'] = {'engines': ['orca']}
    elif case == 'no_route':
        request['calculation'] = None
    elif case == 'resource_allocation':
        request['resources']['cores'] = 3
    # Invalid-request controls deliberately encode raw canonical data rather
    # than replacing or weakening the production encoder's validation.
    raw = canonical_json(request)
    digest = hashlib.sha256(raw).hexdigest()
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    (workspace / 'assignment').symlink_to(root, target_is_directory=True)
    (workspace / 'runner').mkdir()
    program = next(step['run'] for step in _student_admission_workflow()['jobs']['admission']['steps']
                   if step.get('id') == 'failure_publication')
    program_path = workspace / 'failure-publication.py'
    program_path.write_text(program.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0])
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(source_paths(root)),
        PYTHONDONTWRITEBYTECODE='1', RUNNER_TEMP=str(workspace / 'runner'),
        REQUEST_ID=request['request_id'], REQUEST_BASE64=base64.b64encode(raw).decode(),
        REQUEST_SHA256='0' * 64 if case == 'digest' else digest,
        GITHUB_REPOSITORY=request['repository'],
        GITHUB_SHA='0' * 40 if case == 'assignment_source' else request['source_sha'],
        GITHUB_REF='refs/heads/other' if case == 'default_branch' else 'refs/heads/main',
        DEFAULT_BRANCH='main', GITHUB_RUN_ID='1', GITHUB_RUN_ATTEMPT='1',
        GITHUB_OUTPUT=str(workspace / 'github-output'), GITHUB_TOKEN=peer.token,
        COCHEM_APPROVED_BASE_SHA='c' * 40 if case == 'stale_approval' else peer.revision,
        COCHEM_COURSE_CHANNEL='')
    for name in ('GH_TOKEN', 'COCHEM_SOURCE_CREDENTIAL', 'COCHEM_ORCA_ASSET_CREDENTIAL',
                 'COCHEM_CFOUR_ASSET_CREDENTIAL'):
        environment.pop(name, None)
    executed = subprocess.run([sys.executable, '-B', '-c', _STUDENT_ADMISSION_CHILD,
        str(root), str(workspace), f'http://127.0.0.1:{peer.server_port}', mode, case, str(program_path)],
        env=environment, cwd=workspace, capture_output=True, text=True, timeout=30)
    assert peer.token not in executed.stdout + executed.stderr
    assert executed.returncode == 0, executed.stdout + executed.stderr
    assert 'admission-control-passed' in executed.stdout


@pytest.mark.parametrize('route', ['calculation', 'provider', 'capability_probe'])
def test_canonical_admission_classifies_only_verified_requests(project_approval_peer, tmp_path, route):
    _run_student_admission_child(project_approval_peer, tmp_path, route=route)
    assert project_approval_peer.paths == [
        '/repos/ProfJJK-CoChem/CoChem-BASE/commits/' + project_approval_peer.revision]


@pytest.mark.parametrize('case', ['digest', 'dual_route', 'no_route', 'resource_allocation',
    'assignment_source', 'default_branch', 'changed_saved_request', 'stale_approval',
    'wrong_metadata', 'wrong_checkout', 'provider_resources'])
def test_canonical_admission_refuses_unverified_route(project_approval_peer, tmp_path, case):
    _run_student_admission_child(project_approval_peer, tmp_path, case=case,
                                route='provider_resources' if case == 'provider_resources' else 'calculation')


def test_admission_failure_is_sealed_and_retrievable_from_actual_preflight(project_approval_peer, tmp_path):
    _run_student_admission_child(project_approval_peer, tmp_path, mode='failure', case='valid_failure')
    assert len(project_approval_peer.paths) == 1


@pytest.mark.parametrize('case', ['completed', 'operation_true', 'operation_zero', 'probe_performed',
    'wrong_request', 'wrong_repository', 'wrong_source', 'wrong_worker', 'wrong_digest', 'wrong_run',
    'wrong_attempt', 'boolean_run', 'boolean_attempt', 'changed_saved_request', 'saved_cores_float',
    'saved_memory_float', 'oversize_report',
    'post_manifest_boolean', 'post_manifest_identity', 'post_manifest_oversize'])
def test_admission_failure_publication_refuses_unexpected_state(project_approval_peer, tmp_path, case):
    _run_student_admission_child(project_approval_peer, tmp_path, mode='failure', case=case)


def _prepared_engineering_request(client, peer):
    from cochem_base.interfaces import student_actions_admission_git as transport
    request = _request()
    request.update(repository=peer.repository, source_sha=peer.setup_revision, worker_source_sha=peer.revision)
    store = admission_contract.AdmissionStore(transport.GitAdmissionBackend(client, peer.repository))
    snapshot = store.prepare(canonical_json(request), repository_id=17, branch='main', workflow_id=123)
    return store, client._saved_admission(snapshot)


def test_prepared_resume_post_ack_never_returns_the_new_project_generation(project_approval_peer, tmp_path):
    peer = project_approval_peer
    client = project_approval_client(peer, tmp_path)
    store, saved = _prepared_engineering_request(client, peer)
    peer.dispatch_terminal_race = True
    observed = client.resume_prepared_admission(saved)
    assert observed['request_id'] == saved['request_id']
    assert observed['run_id'] == peer.runs[0]['id'] and observed['conclusion'] == 'failure'
    assert observed['admission_terminal'] is True
    assert peer.race_new_submission['request_id'] != saved['request_id']
    assert store.read().intent['request_id'] == peer.race_new_submission['request_id']
    assert store.read().state['phase'] == 'prepared' and not store.read().state['stop_requested']
    assert len(peer.submitted) == 1


def test_bind_cas_exception_never_retargets_status_to_replacement_request(project_approval_peer, tmp_path):
    from cochem_base.interfaces import student_actions_admission_git as transport
    peer = project_approval_peer
    client = project_approval_client(peer, tmp_path)
    store, saved = _prepared_engineering_request(client, peer)
    store.resume(saved['admission_identity']).publish().post(transport.ActionsAdmissionTransport(client))
    saved = client._saved_admission(store.read())
    peer.binding_patch_race = True
    with pytest.raises((admission_contract.AdmissionError, StudentActionsError)):
        client.status(saved)
    assert peer.race_new_submission['request_id'] != saved['request_id']
    assert store.read().intent['request_id'] == peer.race_new_submission['request_id']
    assert store.read().state['phase'] == 'prepared' and not store.read().state['stop_requested']
    assert len(peer.submitted) == 1
    assert any(row.get('refused_after_competing_append') for row in peer.git_writes)


@pytest.mark.parametrize('historical', [False, True])
def test_completed_bound_status_refuses_same_uuid_wrong_returned_run_id(project_approval_peer, tmp_path, historical):
    peer = project_approval_peer
    client = project_approval_client(peer, tmp_path)
    submitted = client.submit(_request()['calculation'])
    actual_id = submitted['run_id']
    peer.runs[0].update(status='completed', conclusion='failure')
    terminal = client.status(submitted)
    assert terminal['admission_terminal'] is True and terminal['run_id'] == actual_id
    if historical:
        newer = _request()
        newer.update(repository=peer.repository, source_sha=peer.setup_revision, worker_source_sha=peer.revision,
                     request_id='ac72d7ea-3c83-425e-9163-e5d5b15d0af2')
        peer.store.prepare(canonical_json(newer), repository_id=17, branch='main', workflow_id=123)
    before = json.loads((tmp_path/'runtime/StudentActions/submissions'/f"{submitted['request_id']}.json").read_bytes())
    peer.admission_run_changes = {'id': actual_id + 200}
    with pytest.raises(StudentActionsError, match='exact saved binding'):
        client.status(terminal)
    after = json.loads((tmp_path/'runtime/StudentActions/submissions'/f"{submitted['request_id']}.json").read_bytes())
    assert after == before
    assert not any(f'/actions/runs/{actual_id}/artifacts' in path for path in peer.paths)
    assert len(peer.submitted) == 1
