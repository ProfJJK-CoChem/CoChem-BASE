"""Actual bare Git/smart-HTTP reader controls; no hosted/chemistry acceptance."""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
from pathlib import Path
import runpy
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import uuid

import pytest

from ci_tools.source_quarantine import source_paths

ROOT = Path(__file__).resolve().parents[2]
if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
    guard = sys.modules.get('ci_tools.source_quarantine')
    assert guard is not None and Path(guard.__file__).resolve() == ROOT/'ci_tools/source_quarantine.py'
    active = getattr(guard, '_active', None)
    assert active is not None and active['copied'] == ROOT
    assert active['original'] == Path(os.environ['COCHEM_SOURCE_QUARANTINE_ORIGINAL']).resolve()
    assert active['evidence'] == Path(os.environ['COCHEM_SOURCE_QUARANTINE_EVIDENCE']).resolve()
    assert active['revision'] == os.environ['COCHEM_SOURCE_QUARANTINE_REVISION']
    startup = sys.modules.get('sitecustomize')
    if startup is not None:
        assert Path(startup.__file__).resolve() == ROOT/'ci_tools/quarantine_startup/sitecustomize.py'
    else:
        assert sys.flags.isolated == 1 and sys.flags.ignore_environment == 1
    assert not guard.loaded_origins(active)['escaped']

from cochem_base.interfaces import student_actions_admission as admission
from cochem_base.interfaces import student_actions_admission_git as rest
from cochem_base.interfaces.student_request import canonical_json
assert Path(admission.__file__).resolve() == ROOT/'src/cochem_base/interfaces/student_actions_admission.py'
assert Path(rest.__file__).resolve() == ROOT/'src/cochem_base/interfaces/student_actions_admission_git.py'
fixtures = runpy.run_path(str(Path(__file__).with_name("test_student_actions_admission.py")),
                         run_name="readonly_native_git_fixtures")
LocalStore, RestHandler = fixtures["GitStore"], fixtures["GitHandler"]
REPOSITORY = "engineering/private-project"
TOKEN = "engineering-readonly-fixture-token"


def configure_smart_git_peer(peer):
    """Attach finite CGI state to a peer whose actual bare store already exists.

    Reusable by integration fixtures: combine SmartGitHTTPMixin with their real
    REST handler, then call this before serving. No repository is copied/moved.
    """
    peer.git_authenticated = peer.git_unauthenticated = 0
    peer.cgi_children, peer.git_handlers = [], []
    peer.block_git = peer.move_after_git = False
    peer.git_entered, peer.git_release = threading.Event(), threading.Event()


class SmartGitHTTPMixin:
    """Actual Git HTTP CGI plus reviewed loopback Git-data REST fixture."""
    def _smart_git(self):
        peer = self.server
        peer.git_handlers.append(threading.current_thread())
        wanted = "Basic " + base64.b64encode(("x-access-token:" + peer.token).encode()).decode()
        if self.headers.get("Authorization") != wanted:
            peer.git_unauthenticated += 1
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="engineering"')
            self.end_headers()
            return
        peer.git_authenticated += 1
        if peer.block_git:
            peer.git_entered.set()
            peer.git_release.wait(timeout=5)
        parsed = urllib.parse.urlsplit(self.path)
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        environment = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C",
            "GIT_PROJECT_ROOT": str(peer.store.path.parent), "GIT_HTTP_EXPORT_ALL": "1",
            "REQUEST_METHOD": self.command,
            "PATH_INFO": '/'+peer.store.path.name+parsed.path.removeprefix('/'+peer.repository+'.git'),
            "QUERY_STRING": parsed.query, "CONTENT_TYPE": self.headers.get("Content-Type", ""),
            "CONTENT_LENGTH": str(len(raw)), "REMOTE_USER": "x-access-token",
            "SERVER_PROTOCOL": "HTTP/1.1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        # Pass genuine Git protocol negotiation, never a manufactured pack.
        if self.headers.get("Git-Protocol"):
            environment["HTTP_GIT_PROTOCOL"] = self.headers["Git-Protocol"]
        child = subprocess.Popen(["/usr/lib/git-core/git-http-backend"], env=environment,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True)
        peer.cgi_children.append(child)
        try:
            output, error = child.communicate(raw, timeout=15)
        except BaseException:
            try:os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:pass
            child.communicate(timeout=2)
            raise
        assert child.returncode == 0, "Actual Git HTTP backend refused the fixture"
        assert peer.token.encode() not in output + error
        header, body = output.split(b"\r\n\r\n", 1)
        lines = header.decode("ascii").split("\r\n")
        status = next((int(line.split()[1]) for line in lines if line.lower().startswith("status:")), 200)
        if peer.move_after_git and parsed.path.endswith("/git-upload-pack"):
            peer.move_after_git = False
            peer.store.stop(admission.identity(peer.store.read()))
        self.send_response(status)
        for line in lines:
            if not line.lower().startswith("status:"):
                name, value = line.split(":", 1)
                self.send_header(name, value.strip())
        self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):pass

    def do_GET(self):
        if self.path.startswith("/" + self.server.repository + ".git/"):
            return self._smart_git()
        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/" + self.server.repository + ".git/"):
            return self._smart_git()
        return super().do_POST()


class NativeGitHandler(SmartGitHTTPMixin, RestHandler):
    protocol_version = 'HTTP/1.0'  # Close each real fixture request/thread deterministically.


@pytest.fixture
def git_peer(tmp_path):
    directory = tmp_path / "remote" / "engineering"
    directory.mkdir(parents=True)
    store = LocalStore.create(directory / "private-project.git")
    peer = http.server.ThreadingHTTPServer(("127.0.0.1", 0), NativeGitHandler)
    peer.daemon_threads = True
    peer.store, peer.repository, peer.repository_id, peer.workflow_id = store, REPOSITORY, 17, 37
    peer.token=TOKEN
    peer.posts, peer.runs, peer.gets, peer.access = [], [], [], []
    peer.protected, peer.cancels, peer.ref_updates, peer.git_writes = [], [], [], []
    peer.lock = threading.Lock()
    peer.drop_ref_ack = peer.drop_dispatch_ack = False
    peer.drop_create_ack = peer.drop_patch_ack = False
    peer.observation_override = None
    peer.listing_extra, peer.listing_change_page = 0, 1
    configure_smart_git_peer(peer)
    thread = threading.Thread(target=peer.serve_forever, daemon=True)
    thread.start()
    try:
        yield peer
    finally:
        peer.git_release.set()
        peer.shutdown();peer.server_close();thread.join(timeout=5)
        assert not thread.is_alive()
        for handler in peer.git_handlers:
            handler.join(timeout=5)
            assert not handler.is_alive()
        for child in peer.cgi_children:
            if child.poll() is None:
                try:os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:pass
            child.wait(timeout=2)


def make_history(peer, count):
    """Actual Git commits with canonical engineering records, validated by reader.

    Direct fixture construction avoids quadratic setup scans. It neither alters
    the production validator nor creates scientific output or native authority.
    """
    previous, generation, raw_request, intent, state = None, None, None, None, None
    source = peer.store.commit({"engineering-source.txt": b"No scientific source authority"}, None)
    worker = peer.store.commit({"engineering-worker.txt": b"No engine or scientific result"}, None)
    for index in range(count):
        phase = index % 4
        if phase == 0:
            generation = str(uuid.uuid4())
            request = {"schema_version": "cochem.student-request/1", "request_id": str(uuid.uuid4()),
                "repository": REPOSITORY, "source_sha": source, "worker_source_sha": worker,
                "submitted_at": "2026-10-31T00:00:00+00:00", "resources": {"cores": 1, "maxcore_mb": 128},
                "calculation": {"unexecuted_engineering_payload": True}, "provider": None,
                "capability_probe": None, "scientific_inputs": None, "data_inputs": None,
                "t9_request": None, "files": {}}
            raw_request = canonical_json(request)
            intent = {"schema_version": "cochem.student-actions-intent/1", "protocol": admission.PROTOCOL,
                "generation": generation, "repository_id": 17, "repository": REPOSITORY,
                "branch": "main", "workflow_id": 37, "workflow_path": ".github/workflows/student_research.yml",
                "request_id": request["request_id"], "payload_sha256": admission.digest(raw_request),
                "request_blob_sha": admission.blob_id(raw_request), "source_sha": source, "worker_source_sha": worker}
            state = {"schema_version": "cochem.student-actions-state/1", "generation": generation,
                "intent_sha256": admission.digest(canonical_json(intent)), "phase": "prepared", "previous": previous,
                "actor": None, "anchor": None, "binding_sha256": None, "stop_requested": False, "terminal": None}
            binding = None
        elif phase == 1:
            state = dict(state, phase="dispatch_intent", previous=previous, actor=str(uuid.uuid4()))
        elif phase == 2:
            anchor = previous
            binding = {"schema_version": "cochem.student-actions-binding/1", "generation": generation,
                "intent_sha256": state["intent_sha256"], "anchor": anchor,
                **{key: intent[key] for key in ("request_id", "payload_sha256", "repository_id", "repository",
                    "workflow_id", "branch", "source_sha", "worker_source_sha")}, "run_id": 100 + index, "run_attempt": 1}
            state = dict(state, phase="bound", previous=previous, anchor=anchor,
                         binding_sha256=admission.digest(canonical_json(binding)))
        else:
            state = dict(state, phase="terminal", previous=previous,
                terminal={"kind": "confirmed_run_terminal", "run_id": binding["run_id"],
                          "run_attempt": 1, "conclusion": "failure"})
        files = {"request.json": raw_request, "intent.json": canonical_json(intent), "state.json": canonical_json(state)}
        if binding is not None:files["binding.json"] = canonical_json(binding)
        commit = peer.store.commit(files, previous)
        peer.store.advance(commit, previous)
        previous = commit
    return previous


def owned_zombie_control(directory):
    """Real bounded lifecycle fault; invoked from this reviewed test path only.

    Fork before setsid: the child stays in the genuine Git launcher's group,
    while its still-owned parent temporarily retains the exited child elsewhere.
    This forces an actual pending zombie, not a fabricated /proc/exit observation.
    """
    directory = Path(directory)
    ready, release = directory/'ready', directory/'release'
    own = Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    parent = {'pid':os.getpid(),'start_ticks':own[19]}
    (directory/'parent.json').write_text(json.dumps(parent))
    zombie = os.fork()
    if zombie == 0:
        deadline = time.monotonic()+5
        while not ready.exists() and time.monotonic()<deadline:time.sleep(.01)
        os._exit(0)
    try:
        fields = Path(f'/proc/{zombie}/stat').read_text().rsplit(')',1)[1].split()
        parent.update(zombie_pid=zombie,zombie_start_ticks=fields[19])
        staged = directory/'parent.tmp'
        staged.write_text(json.dumps(parent));staged.rename(directory/'parent.json')
        os.setsid()
        ready.touch(exist_ok=False)
        deadline = time.monotonic()+5
        while True:
            fields = Path(f'/proc/{zombie}/stat').read_text().rsplit(')',1)[1].split()
            if fields[0]=='Z':break
            if time.monotonic()>=deadline:raise RuntimeError('Actual lifecycle child did not exit')
            time.sleep(.01)
        own = Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
        record = {'pid':os.getpid(),'start_ticks':own[19],'process_group':os.getpgrp(),
            'session':os.getsid(0),'zombie_pid':zombie,'zombie_start_ticks':fields[19],
            'zombie_group':int(fields[2]),'zombie_session':int(fields[3]),'actual_zombie_state':fields[0]}
        staged = directory/'control.tmp'
        staged.write_text(json.dumps(record));staged.rename(directory/'control.json')
        deadline = time.monotonic()+12
        while not release.exists() and time.monotonic()<deadline:time.sleep(.01)
    finally:
        collected,status = os.waitpid(zombie,0)
        (directory/'reaped.json').write_text(json.dumps({'pid':collected,'status':status}))


CHILD = r'''
import ctypes,json,os,shlex,signal,sys,time
from pathlib import Path
source,url,mode,work,output=sys.argv[1:]
source,work,output=Path(source),Path(work),Path(output)
if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
    assert Path(sys.modules['sitecustomize'].__file__).resolve()==source/'ci_tools/quarantine_startup/sitecustomize.py'
    guard=sys.modules['ci_tools.source_quarantine'];assert guard._active['copied']==source
from ci_tools.source_quarantine import source_paths
assert all(value in sys.path for value in source_paths(source))
from cochem_base.interfaces import student_actions_admission as contract
from cochem_base.interfaces import student_actions_admission_git as rest
from cochem_base.interfaces.student_actions_admission_git_readonly import ReadOnlyGitAdmissionBackend
assert Path(sys.modules[ReadOnlyGitAdmissionBackend.__module__].__file__).resolve()==source/'src/cochem_base/interfaces/student_actions_admission_git_readonly.py'
deadline=time.time()+(2 if mode=='timeout' else 25)
api=rest.ReadOnlyAPI(os.environ['GITHUB_TOKEN'],deadline=deadline,api_url=url,allow_loopback=True)
reader=ReadOnlyGitAdmissionBackend(api,'engineering/private-project',work_root=work,deadline=deadline,
    github_token_from_env='GITHUB_TOKEN',engineering_git_url=url+'/engineering/private-project.git',allow_loopback=True)
def actual_subreaper_bit():
    value=ctypes.c_int()
    if ctypes.CDLL(None,use_errno=True).prctl(37,ctypes.byref(value),0,0,0)!=0:
        raise OSError(ctypes.get_errno(),'Cannot inspect actual process subreaper bit')
    return value.value
initial_subreaper_bit=actual_subreaper_bit()
initial_sigchld_handler=signal.getsignal(signal.SIGCHLD)
if mode in ('lease-threaded','lease-child','lease-nested'):
    import threading,subprocess
    event=threading.Event();thread=None;existing=None;outer=False;refused=False
    try:
        target=reader
        if mode=='lease-threaded':
            thread=threading.Thread(target=lambda:event.wait(timeout=5));thread.start()
            assert len(list(Path('/proc/self/task').iterdir()))>1
        elif mode=='lease-child':
            existing=subprocess.Popen(['/bin/sleep','10'],start_new_session=True)
            existing_ticks=Path(f'/proc/{existing.pid}/stat').read_text().rsplit(')',1)[1].split()[19]
        else:
            reader.__enter__();outer=True
            target=ReadOnlyGitAdmissionBackend(api,'engineering/private-project',work_root=work/'nested',deadline=deadline,
                engineering_git_url=url+'/engineering/private-project.git',allow_loopback=True)
        bit_before_attempt=actual_subreaper_bit()
        try:target.__enter__()
        except contract.AdmissionError as error:
            expected={'lease-threaded':'Admission metadata requires exactly one OS thread',
                'lease-child':'Admission metadata requires no existing children',
                'lease-nested':'Only one isolated admission metadata context may be active'}[mode]
            assert str(error)==expected,'Lease refused for a different, unqualified reason'
            refused=True
        else:
            target.__exit__(None,None,None)
            raise AssertionError('Unsupported metadata lease entry was accepted')
        assert refused and target._root is None and actual_subreaper_bit()==bit_before_attempt
        if mode=='lease-threaded':assert len(target._lease.entry_tasks)>1
        if mode=='lease-child':assert any(row['pid']==existing.pid and row['start_ticks']==existing_ticks
            for row in target._lease.entry_children)
    finally:
        event.set()
        if thread is not None:thread.join(timeout=2);assert not thread.is_alive()
        if existing is not None:
            fields=Path(f'/proc/{existing.pid}/stat').read_text().rsplit(')',1)[1].split()
            assert fields[19]==existing_ticks and int(fields[2])==existing.pid and int(fields[3])==existing.pid
            os.kill(existing.pid,signal.SIGTERM)
            existing.wait(timeout=2)
        if outer:reader.__exit__(None,None,None)
    assert actual_subreaper_bit()==initial_subreaper_bit
    assert signal.getsignal(signal.SIGCHLD)==initial_sigchld_handler
    assert sys.modules[ReadOnlyGitAdmissionBackend.__module__]._ACTIVE_LEASE is None
    output.write_text(json.dumps({'engineering_only':True,'mode':mode,'positive':False,'refused':refused,
        'prior_subreaper_bit':initial_subreaper_bit,'restored_subreaper_bit':actual_subreaper_bit(),
        'no_scientific_operation':True},indent=2)+'\n')
    raise SystemExit(0)
if mode=='cleanup-hold':
    libc=ctypes.CDLL(None,use_errno=True)
    previous=ctypes.c_int()
    if libc.prctl(37,ctypes.byref(previous),0,0,0)!=0:raise OSError(ctypes.get_errno(),'Cannot inspect actual subreaper')
    if libc.prctl(36,1,0,0,0)!=0:raise OSError(ctypes.get_errno(),'Cannot own actual orphan cleanup control')
    work.mkdir(mode=0o700)
    directory=work/'lifecycle-control';directory.mkdir(mode=0o700)
    control=None;child=None;entered=False;exited=False;actual_reaped=[];signal_attempts=[]
    def collect_exact(pid,ticks):
        limit=time.monotonic()+5
        signaled=False
        while True:
            try:collected,status=os.waitpid(pid,os.WNOHANG)
            except ChildProcessError:
                raise AssertionError('Actual controlled descendant was not owned for reaping')
            if collected:
                actual_reaped.append({'pid':collected,'status':status});return status
            fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
            assert fields[19]==ticks,'Refusing cleanup of a reused fixture PID'
            if time.monotonic()>=limit:
                if signaled:raise AssertionError('Actual controlled fixture did not stop')
                # Only this identity-bound actual fixture PID, never a broad group.
                os.kill(pid,signal.SIGKILL);signaled=True;limit=time.monotonic()+2
            time.sleep(.01)
    try:
        reader.__enter__();entered=True
        forwarded={name:value for name,value in os.environ.items() if name.startswith('COCHEM_SOURCE_QUARANTINE_')}
        forwarded.update(PYTHONPATH=os.pathsep.join(source_paths(source)),PYTHONDONTWRITEBYTECODE='1',PYTHONOPTIMIZE='0',PYTHONNOUSERSITE='1')
        invocation=['env',*[name+'='+value for name,value in forwarded.items()],sys.executable,'-B','-c',
            "import runpy,sys;runpy.run_path(sys.argv[1],run_name='actual_owned_lifecycle_control')['owned_zombie_control'](sys.argv[2])",
            str(source/'tests/base/test_student_actions_admission_git_readonly.py'),str(directory)]
        alias='!'+' '.join(shlex.quote(value) for value in invocation)
        child=sys.modules[ReadOnlyGitAdmissionBackend.__module__]._GitChild(reader,
            ['-c','alias.cochem-owned-lifecycle='+alias,'cochem-owned-lifecycle'])
        limit=time.monotonic()+5
        while not (directory/'control.json').exists():
            assert time.monotonic()<limit,'Actual lifecycle control did not become ready'
            time.sleep(.01)
        control=json.loads((directory/'control.json').read_bytes())
        assert control['zombie_group']==control['zombie_session']==child.pid
        assert control['process_group']==control['session']==control['pid']
        assert control['actual_zombie_state']=='Z'
        def observe_owned_signals(event,args):
            if event=='os.killpg':signal_attempts.append({'process_group':args[0],'signal':args[1]})
        sys.addaudithook(observe_owned_signals)
        first_signal_count=None
        for attempt in range(2):
            try:child.close()
            except contract.AdmissionError:pass
            else:raise AssertionError('Actual pending zombie was hidden by cleanup')
            assert child.closed and child.record['stopped'] is False
            assert child.record['leader_reaped_after_group_inspection'] is True
            assert any(row['pid']==control['zombie_pid'] and row['start_ticks']==control['zombie_start_ticks']
                for row in child.record['external_reaping_pending'])
            assert reader._root.exists()
            if attempt==0:first_signal_count=len(signal_attempts)
            else:assert len(signal_attempts)==first_signal_count,'Repeated close tried to signal a reaped group'
        try:reader.__exit__(None,None,None)
        except contract.AdmissionError:exited=True
        else:raise AssertionError('Context hid its prior incomplete Git cleanup')
        assert reader.diagnostics[-1]['context_closed'] is False and reader._root.exists()
        assert reader._token is None
        assert len(signal_attempts)==first_signal_count
        assert actual_subreaper_bit()==1 and reader._lease.restored
    finally:
        (directory/'release').touch(exist_ok=True)
        if entered and not exited:
            try:reader.__exit__(None,None,None)
            except contract.AdmissionError:pass
        cleanup_control=control
        if cleanup_control is None and (directory/'parent.json').exists():
            cleanup_control=json.loads((directory/'parent.json').read_bytes())
        if cleanup_control is not None:
            status=collect_exact(cleanup_control['pid'],cleanup_control['start_ticks'])
            # If emergency cleanup interrupted the real parent's wait, reap only
            # actual identity-bound adopted children. Git's intermediate shell
            # can also be pending; never erase the failed production diagnostics.
            pending={row['pid']:row['start_ticks'] for row in (child.record.get('external_reaping_pending',[]) if child is not None else [])}
            if 'zombie_pid' in cleanup_control:
                pending[cleanup_control['zombie_pid']]=cleanup_control['zombie_start_ticks']
            for pid,ticks in pending.items():
                try:fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
                except FileNotFoundError:continue
                assert fields[19]==ticks,'Refusing cleanup of a reused pending fixture PID'
                assert int(fields[1])==os.getpid(),'Pending fixture is not actually adopted by this subreaper'
                collect_exact(pid,ticks)
            if control is not None:assert status==0 and (directory/'reaped.json').exists()
        if libc.prctl(36,previous.value,0,0,0)!=0:raise OSError(ctypes.get_errno(),'Cannot restore own subreaper state')
    assert control is not None and exited and actual_reaped
    assert child._members()==[]
    output.write_text(json.dumps({'engineering_only':True,'mode':mode,'positive':False,'refused':True,
        'actual_lifecycle_control':control,'actual_reaped':actual_reaped,'diagnostics':reader.diagnostics,
        'actual_group_signal_attempts':signal_attempts,
        'incomplete_cleanup_sticky':True,'staging_retained':reader._root.exists(),'no_scientific_operation':True},indent=2)+'\n')
    raise SystemExit(0)
diagnostic_records=[];diagnostic_publication_errors=[]
diagnostic_phase='before-context-entry';diagnostic_caught_error=None
def diagnostic_error_chain(error):
    categories={
        'The inherited admission metadata deadline expired':'inherited-deadline-expired',
        'The bounded native Git metadata operation failed; no request was admitted':'git-operation-refused',
        'Native Git metadata process-group cleanup could not be confirmed':'group-cleanup-unconfirmed',
        'Native Git metadata cleanup previously failed; its staging remains held':'prior-cleanup-failure-sticky',
        'Owned native Git metadata cleanup was incomplete':'context-cleanup-incomplete',
        'Native Git metadata owner identity was lost before cleanup':'cleanup-owner-identity-unconfirmed',
        'Refusing to signal a Git metadata group after identity loss':'signal-owner-identity-unconfirmed'}
    chain=[];seen=set()
    while error is not None and id(error) not in seen and len(chain)<8:
        seen.add(id(error))
        category=categories.get(str(error),'other-admission-refusal') if type(error) is contract.AdmissionError else 'other-exception'
        row={'class':type(error).__name__,'approved_category':category}
        status=vars(error).get('http_status',vars(error).get('code'))
        if type(status) is int and 100<=status<=599:row['http_status']=status
        chain.append(row)
        error=error.__cause__ if error.__cause__ is not None else error.__context__
    return chain
def diagnostic_proc(pid,ticks):
    if type(pid) is not int or pid<=0:return {'invalid_pid':True}
    try:
        fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        return {'observed_after_unwind_only':True,'exists':True,'identity_matches':fields[19]==ticks,
            'current_start_ticks':fields[19],'state':fields[0],'parent_pid':int(fields[1]),
            'process_group':int(fields[2]),'session':int(fields[3])}
    except FileNotFoundError:return {'observed_after_unwind_only':True,'exists':False}
    except (OSError,ValueError,IndexError) as error:return {'observation_error_class':type(error).__name__}
def diagnostic_checkpoint(label):
    try:
        allowed={'pid','process_group','start_ticks','hard_per_file_bytes','hard_address_space_bytes',
            'started_monotonic','stopped','identity_lost','leader_state_before_cleanup',
            'waitid_completion_observed_before_cleanup','exit_code','stdout_bytes','stderr_bytes',
            'raw_output_logged','actual_file_limit_error_observed','actual_file_limit_signal_observed','cleanup_leader_identity_verified_before_signals',
            'leader_reaped_after_group_inspection','elapsed_seconds','context_closed','entry_failed',
            'owned_root_removed','token_cleared','credentials_persisted','bare_repository_uploaded'}
        rows=[]
        for original in reader.diagnostics[:32]:
            row={key:value for key,value in original.items() if key in allowed}
            pending=original.get('external_reaping_pending',[])
            if 'external_reaping_pending' in original:
                row['external_reaping_pending_count']=len(pending)
                row['external_reaping_pending']=[{key:item[key] for key in ('pid','state','start_ticks') if key in item}
                    for item in pending[:64]]
                for item in row['external_reaping_pending']:
                    item['checkpoint_observation']=diagnostic_proc(item.get('pid'),item.get('start_ticks'))
            if 'cleanup_errors' in original:row['cleanup_error_classes']=original['cleanup_errors'][:32]
            if 'adopted_reaped' in original:row['adopted_reaped']=original['adopted_reaped'][:64]
            if 'subreaper_lease' in original:row['subreaper_lease']=original['subreaper_lease']
            if 'pid' in row:row['checkpoint_observation']=diagnostic_proc(row['pid'],row.get('start_ticks'))
            rows.append(row)
        root_state={'assigned':reader._root is not None,'token_cleared':reader._token is None}
        if reader._root is not None:
            try:
                info=reader._root.lstat()
                root_state.update(exists=True,original_identity_matches=(info.st_dev,info.st_ino)==reader._root_identity)
            except FileNotFoundError:root_state['exists']=False
        active_error=sys.exc_info()[1]
        diagnostic_records.append({'checkpoint':label,'epoch':time.time(),'phase':diagnostic_phase,'mode':mode,
            'passed_operand':passed,'refused_operand':refused,'diagnostics_truthy_operand':bool(reader.diagnostics),
            'all_stopped_operand':all(row.get('stopped',True) for row in reader.diagnostics),
            'diagnostics_count':len(reader.diagnostics),'rows':rows,'rows_truncated':len(reader.diagnostics)>32,
            'root_state':root_state,'active_exception_chain':diagnostic_error_chain(active_error),
            'caught_exception_chain':diagnostic_error_chain(diagnostic_caught_error)})
        raw=json.dumps({'scope':'Diagnostic engineering only; unchanged assertions/production/cleanup',
            'records':diagnostic_records,'publication_error_classes':diagnostic_publication_errors},indent=2,allow_nan=False)+'\n'
        assert os.environ['GITHUB_TOKEN'] not in raw,'Diagnostic must not contain credential bytes'
        stage=output.with_suffix('.diagnostic.tmp')
        with stage.open('x') as handle:handle.write(raw)
        stage.replace(output.with_suffix('.diagnostic.json'))
    except BaseException as error:
        diagnostic_publication_errors.append(type(error).__name__)
        os.write(2,b'[DIAGNOSTIC_PUBLICATION_FAILED; original assertion/error still follows]\n')
passed=False;refused=False;notice=''
permission_control={'hit':False}
if mode=='entry-permission':
    assert os.geteuid()!=0,'Genuine unprivileged directory permission control required'
    def remove_owned_directory_write(event,args):
        if event=='open' and not permission_control['hit'] and isinstance(args[0],(str,bytes)):
            target=Path(os.fsdecode(args[0]))
            if target.name=='askpass' and target.parent.parent==work:
                permission_control['hit']=True;target.parent.chmod(0o500)
    sys.addaudithook(remove_owned_directory_write)
try:
    with reader:
        diagnostic_phase='reading-complete-history'
        store=contract.AdmissionStore(reader)
        snapshot=store.read()
        diagnostic_phase='after-complete-history'
        if mode=='positive':
            assert snapshot is not None and reader.tip()==snapshot.tip
            assert snapshot.state['phase']=='terminal'
            for call in (lambda:reader.commit({},None),lambda:reader.advance('a'*40,None)):
                try:call()
                except contract.AdmissionError:pass
                else:raise AssertionError('Readonly backend admitted mutation')
            assert 'GITHUB_TOKEN' not in reader._environment(False) and 'COCHEM_ADMISSION_GIT_TOKEN' not in reader._environment(False)
            assert reader._environment(False)['HOME']==os.environ['HOME']
            for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY','http_proxy','https_proxy','all_proxy','no_proxy'):
                assert reader._environment(False).get(key)==os.environ.get(key)
            actual_limits=Path(f'/proc/{reader._batch.pid}/limits').read_text().splitlines()
            assert any(line.startswith('Max file size') and line.split()[3:5]==['33554432','33554432'] for line in actual_limits)
            assert any(line.startswith('Max address space') and line.split()[3:5]==['536870912','536870912'] for line in actual_limits)
            assert Path(f'/proc/{reader._batch.pid}/exe').resolve()==Path('/usr/bin/git')
            for path in reader._root.rglob('*'):
                if path.is_file():assert os.environ['GITHUB_TOKEN'].encode() not in path.read_bytes()
            passed=True
        else:
            raise AssertionError('Negative real Git transport/history unexpectedly admitted')
except (contract.AdmissionError,PermissionError) as error:
    diagnostic_caught_error=error
    refused=True;notice=str(error)
    assert mode!='positive',notice
finally:
    diagnostic_checkpoint('after-context-unwind')
assert (passed and not refused) if mode=='positive' else refused
diagnostic_checkpoint('before-common-cleanup-assertions')
assert actual_subreaper_bit()==initial_subreaper_bit
assert signal.getsignal(signal.SIGCHLD)==initial_sigchld_handler
assert sys.modules[ReadOnlyGitAdmissionBackend.__module__]._ACTIVE_LEASE is None
assert reader.diagnostics and all(row.get('stopped',True) for row in reader.diagnostics)
if mode=='entry-permission':
    assert permission_control['hit'] and reader.diagnostics[-1]['owned_root_removed'] and reader._token is None
else:
    assert reader.diagnostics[-1]['context_closed'] is True
    assert all(row.get('cleanup_leader_identity_verified_before_signals',True) and not row.get('external_reaping_pending') for row in reader.diagnostics)
    for row in reader.diagnostics:
        if 'pid' not in row:continue
        try:current=Path(f"/proc/{row['pid']}/stat").read_text().rsplit(')',1)[1].split()[19]
        except FileNotFoundError:continue
        assert current!=row['start_ticks'],'Exact old metadata leader was not reaped'
    if mode=='positive':assert any(row.get('leader_state_before_cleanup')=='Z' and row.get('waitid_completion_observed_before_cleanup') for row in reader.diagnostics)
assert not diagnostic_publication_errors,'Diagnostic publication failed independently of original assertions'
output.write_text(json.dumps({'engineering_only':True,'mode':mode,'positive':passed,'refused':refused,
    'notice':notice,'diagnostics':reader.diagnostics,'no_scientific_operation':True,
    'prior_subreaper_bit':initial_subreaper_bit,'restored_subreaper_bit':actual_subreaper_bit()},indent=2)+'\n')
'''


def exercise(peer, tmp_path, mode="positive", *, number=0, extra_environment=None):
    output, work = tmp_path / f"result-{number}.json", tmp_path / f"objects-{number}"
    before = peer.store.tip()
    environment = dict(os.environ, GITHUB_TOKEN=TOKEN, PYTHONDONTWRITEBYTECODE="1", PYTHONOPTIMIZE="0",
                       PYTHONPATH=os.pathsep.join(source_paths(ROOT)),
                       OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',
                       NO_PROXY='127.0.0.1,localhost,::1',no_proxy='127.0.0.1,localhost,::1')
    environment.update(extra_environment or {})
    result = subprocess.run([sys.executable, "-B", "-c", CHILD, str(ROOT),
        f"http://127.0.0.1:{peer.server_port}", mode, str(work), str(output)],
        env=environment, capture_output=True, text=True, timeout=35)
    assert TOKEN not in result.stdout + result.stderr
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(output.read_bytes())
    assert TOKEN not in output.read_text()
    assert peer.store.tip() == before or mode == "moving"
    if mode=='cleanup-hold':
        assert receipt['staging_retained'] and len(list(work.glob('readonly-*')))==1
    else:assert not list(work.glob("readonly-*"))
    return receipt


def test_three_cold_native_git_readers_over_real80_commit_history(git_peer, tmp_path):
    peer = git_peer
    make_history(peer, 80)
    before = len(peer.gets)
    receipts = [exercise(peer, tmp_path, number=number) for number in range(3)]
    ledger_calls = peer.gets[before:]
    # Every actual read is a fresh ref; no per-object REST history traversal.
    assert ledger_calls and all(path.endswith('/git/ref/heads/cochem-student-admission-v1') for path in ledger_calls)
    assert len(ledger_calls) == 12  # initial, postfetch, postverify, final caller per process.
    assert peer.git_authenticated >= 3 and peer.git_unauthenticated >= 3
    assert all(any(row.get('commits') == 80 for row in receipt['diagnostics']) for receipt in receipts)
    assert peer.posts == peer.protected == peer.cancels == peer.git_writes == []


@pytest.mark.parametrize('count,mode', [(256, 'positive'), (257, 'history-overflow'), (260, 'shallow')])
def test_complete_real_history_preserves256_limit_and_refuses_shallow_boundary(git_peer, tmp_path, count, mode):
    make_history(git_peer, count)
    receipt = exercise(git_peer, tmp_path, mode)
    assert receipt['positive'] is (mode == 'positive')


@pytest.mark.parametrize('case', ['oversized-member', 'unknown-member', 'merge'])
def test_malformed_actual_git_graph_is_refused_without_changing_request(git_peer, tmp_path, case):
    peer = git_peer
    make_history(peer, 4)
    old = peer.store.tip();files,parent = peer.store.files(old)
    if case == 'oversized-member':files['request.json'] = b'x' * (50 * 1024 + 1)
    elif case == 'unknown-member':files['unknown.txt'] = b'not allowed'
    if case == 'merge':
        unused, tree = peer.store.git('rev-parse',old+'^{tree}')
        unused, raw = peer.store.git('commit-tree',tree.decode().strip(),'-p',old,'-p',parent,data=b'Engineering malformed merge\n')
        corrupt=raw.decode().strip()
    else:corrupt=peer.store.commit(files,old)
    peer.store.git('update-ref',peer.store.ref,corrupt,old)
    receipt=exercise(peer,tmp_path,case)
    assert receipt['refused'] and peer.store.tip()==corrupt


def test_actual_native_git_deadline_refuses_waiting_transport_and_stops_owned_groups(git_peer, tmp_path):
    make_history(git_peer,4)
    git_peer.block_git=True
    receipt=exercise(git_peer,tmp_path,'timeout')
    assert receipt['refused'] and git_peer.git_entered.is_set()


def test_actual_git_http_authentication_refusal_never_falls_back_to_rest_history(git_peer, tmp_path):
    make_history(git_peer, 4)
    git_peer.token = 'different-engineering-server-token'
    before = len(git_peer.gets)
    receipt = exercise(git_peer, tmp_path, 'authentication')
    assert receipt['refused'] and git_peer.git_unauthenticated >= 1
    assert git_peer.git_authenticated == 0
    assert git_peer.gets[before:] == ['/repos/'+REPOSITORY+'/git/ref/heads/cochem-student-admission-v1']
    assert git_peer.posts == git_peer.protected == git_peer.git_writes == []


def test_fresh_ref_movement_during_real_fetch_holds_original_request(git_peer, tmp_path):
    make_history(git_peer,2)
    git_peer.move_after_git=True
    receipt=exercise(git_peer,tmp_path,'moving')
    assert receipt['refused'] and git_peer.store.read().state['stop_requested'] is True


def test_entry_permission_failure_removes_exact_owned_root_and_clears_token(git_peer,tmp_path):
    make_history(git_peer,4)
    before=len(git_peer.gets)
    receipt=exercise(git_peer,tmp_path,'entry-permission')
    assert receipt['refused'] and len(git_peer.gets)==before and git_peer.git_authenticated==0


def test_actual_pending_zombie_cleanup_failure_stays_sticky_and_retains_staging(git_peer,tmp_path):
    receipt=exercise(git_peer,tmp_path,'cleanup-hold')
    assert receipt['incomplete_cleanup_sticky'] and receipt['staging_retained']
    assert receipt['diagnostics'][-1]['context_closed'] is False
    assert git_peer.gets==[] and git_peer.git_authenticated==0


@pytest.mark.parametrize('mode',['lease-threaded','lease-child','lease-nested'])
def test_actual_process_lease_refuses_unsupported_entry_and_restores_prior_bit(git_peer,tmp_path,mode):
    receipt=exercise(git_peer,tmp_path,mode)
    assert receipt['refused'] and receipt['prior_subreaper_bit']==receipt['restored_subreaper_bit']
    assert git_peer.gets==[] and git_peer.git_authenticated==0


def test_real_incompressible_git_pack_hits_kernel_per_file_limit(git_peer,tmp_path):
    peer=git_peer;make_history(peer,4)
    old=peer.store.tip();files,unused=peer.store.files(old)
    # This is deliberately unrelated engineering data, never scientific input.
    files['request.json']=os.urandom(33*1024*1024)
    bad=peer.store.commit(files,old);peer.store.git('update-ref',peer.store.ref,bad,old)
    receipt=exercise(peer,tmp_path,'file-limit')
    assert receipt['refused'] and any(row.get('actual_file_limit_error_observed') or
        any(child['signaled'] and child['signal']==signal.SIGXFSZ and os.WIFSIGNALED(child['raw_wait_status'])
            and os.WTERMSIG(child['raw_wait_status'])==signal.SIGXFSZ for child in row.get('adopted_reaped',[]))
        for row in receipt['diagnostics'])
    assert peer.store.tip()==bad


def test_ambient_git_configuration_hooks_objectdirs_and_trace_are_not_used(git_peer,tmp_path):
    make_history(git_peer,4)
    poison=tmp_path/'poison';poison.mkdir();hooks=poison/'hooks';hooks.mkdir()
    marker=poison/'hook-ran'
    hook=hooks/'reference-transaction';hook.write_text('#!/bin/sh\nprintf attacked > '+str(marker)+'\n');hook.chmod(0o700)
    config=poison/'config';config.write_text('[core]\n hooksPath = '+str(hooks)+'\n')
    trace=poison/'trace'
    env={'GIT_CONFIG_GLOBAL':str(config),'GIT_CONFIG_SYSTEM':str(config),
        'GIT_CONFIG_COUNT':'1','GIT_CONFIG_KEY_0':'core.hooksPath','GIT_CONFIG_VALUE_0':str(hooks),
        'GIT_OBJECT_DIRECTORY':str(poison/'wrong-objects'),'GIT_ALTERNATE_OBJECT_DIRECTORIES':str(poison),
        'GIT_TEMPLATE_DIR':str(poison),'GIT_TRACE':str(trace),'GIT_CURL_VERBOSE':'1'}
    receipt=exercise(git_peer,tmp_path,extra_environment=env)
    assert receipt['positive'] and not marker.exists() and not trace.exists()
