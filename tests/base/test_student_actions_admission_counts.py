"""Actual local Git/HTTP metadata costs; no hosted rate or scientific acceptance.

The full worker barrier has separate actual-child controls. Here its metadata
sequence is measured with three fresh authenticated API/backend instances;
request construction below is engineering Git history, never engine output.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time
import uuid

import pytest

from ci_tools.source_quarantine import source_paths
from cochem_base.interfaces import student_actions_admission as admission
from cochem_base.interfaces import student_actions_admission_git as rest
from cochem_base.interfaces import student_actions_admission_git_readonly as reader

ROOT = Path(__file__).resolve().parents[2]
_contracts = runpy.run_path(str(Path(__file__).with_name('test_student_actions_contract.py')),
                          run_name='native_git_counter_contract_fixture')
_cache = runpy.run_path(str(Path(__file__).with_name('test_student_actions_admission_cache.py')),
                      run_name='native_git_counter_cache_fixture')
project_approval_peer = _contracts['project_approval_peer']


def append_bound_job(peer, revision, index):
    """Finish prior engineering run as failure, then append one new real graph.

    After N calls there are 4*N-1 transitions: N-1 completed failures and one
    bound, unexecuted request. No source ref is rewritten or science performed.
    """
    store, backend = peer.store, peer.store.backend
    old = store.read()
    parent = old.tip if old else None
    if old:
        files, unused_parent = backend.files(parent)
        state = admission.strict(files['state.json'])
        assert state['phase'] == 'bound'
        state.update(phase='terminal', previous=parent, terminal={
            'kind': 'confirmed_run_terminal', 'run_id': old.binding['run_id'],
            'run_attempt': 1, 'conclusion': 'failure'})
        files['state.json'] = admission.canonical(state)
        commit = backend.commit(files, parent)
        backend.advance(commit, parent)
        parent = commit
        next(run for run in peer.runs if run['id'] == old.binding['run_id']).update(
            status='completed', conclusion='failure')
    request = _contracts['_request']()
    request.update(repository=peer.repository, source_sha=revision, worker_source_sha=revision,
                   request_id=str(uuid.uuid5(uuid.NAMESPACE_URL, 'counter-request-'+str(index))))
    raw = admission.canonical(request)
    intent = {'schema_version': 'cochem.student-actions-intent/1', 'protocol': admission.PROTOCOL,
        'generation': str(uuid.uuid5(uuid.NAMESPACE_URL, 'counter-generation-'+str(index))),
        'repository_id': 17, 'repository': peer.repository, 'branch': 'main', 'workflow_id': 123,
        'workflow_path': '.github/workflows/student_research.yml', 'request_id': request['request_id'],
        'payload_sha256': admission.digest(raw), 'request_blob_sha': admission.blob_id(raw),
        'source_sha': revision, 'worker_source_sha': revision}
    state = {'schema_version': 'cochem.student-actions-state/1', 'generation': intent['generation'],
        'intent_sha256': admission.digest(admission.canonical(intent)), 'phase': 'prepared',
        'previous': parent, 'actor': None, 'anchor': None, 'binding_sha256': None,
        'stop_requested': False, 'terminal': None}
    files = {'request.json': raw, 'intent.json': admission.canonical(intent),
             'state.json': admission.canonical(state)}
    commit = backend.commit(files, parent)
    backend.advance(commit, parent)
    parent = commit
    state.update(phase='dispatch_intent', previous=parent,
        actor=str(uuid.uuid5(uuid.NAMESPACE_URL, 'counter-actor-'+str(index))))
    files['state.json'] = admission.canonical(state)
    anchor = backend.commit(files, parent)
    backend.advance(anchor, parent)
    binding = {'schema_version': 'cochem.student-actions-binding/1',
        'generation': intent['generation'], 'intent_sha256': state['intent_sha256'], 'anchor': anchor,
        **{key: intent[key] for key in ('request_id', 'payload_sha256', 'repository_id', 'repository',
            'workflow_id', 'branch', 'source_sha', 'worker_source_sha')},
        'run_id': 5000+index, 'run_attempt': 1}
    files['binding.json'] = admission.canonical(binding)
    state.update(phase='bound', previous=anchor, anchor=anchor,
                 binding_sha256=admission.digest(files['binding.json']))
    files['state.json'] = admission.canonical(state)
    bound = backend.commit(files, anchor)
    backend.advance(bound, anchor)
    peer.runs.append({'id': binding['run_id'], 'run_attempt': 1, 'workflow_id': 123,
        'repository': {'id': 17, 'full_name': peer.repository}, 'event': 'workflow_dispatch',
        'display_title': 'CoChem student '+request['request_id'], 'head_branch': 'main',
        'head_sha': revision, 'status': 'queued', 'conclusion': None,
        'html_url': f"https://github.com/{peer.repository}/actions/runs/{binding['run_id']}"})
    return store.read()


def actual_gets(peer, first_paths, first_git):
    paths = peer.paths[first_paths:] + [value for value in peer.gets[first_git:] if isinstance(value, str)]
    counts = {'capability': 0, 'project': 0, 'run': 0, 'workflow': 0, 'ref': 0, 'ledger_object': 0}
    for path in paths:
        if '/contents/' in path:
            counts['capability'] += 1
        elif '/git/ref/' in path:
            counts['ref'] += 1
        elif any(part in path for part in ('/git/commits/', '/git/trees/', '/git/blobs/')):
            counts['ledger_object'] += 1
        elif '/actions/runs/' in path:
            counts['run'] += 1
        elif '/actions/workflows/' in path:
            counts['workflow'] += 1
        elif path == '/repos/'+peer.repository:
            counts['project'] += 1
        else:
            raise AssertionError('Unclassified actual metadata GET: '+path)
    return counts


COLD_CHILD = r"""
import hashlib,json,os,runpy,sys,time
from pathlib import Path
source,expected_path,expected_hash,url,work_root,result_path=sys.argv[1:]
source,expected_path,work_root,result_path=map(Path,(source,expected_path,work_root,result_path))
if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
    startup=sys.modules.get('sitecustomize')
    assert startup is not None and Path(startup.__file__).resolve()==source/'ci_tools/quarantine_startup/sitecustomize.py'
    guard=sys.modules.get('ci_tools.source_quarantine')
    assert guard is not None and Path(guard.__file__).resolve()==source/'ci_tools/source_quarantine.py'
    active=getattr(guard,'_active',None)
    assert active is not None and active['copied']==source
    assert active['original']==Path(os.environ['COCHEM_SOURCE_QUARANTINE_ORIGINAL']).resolve()
    assert active['evidence']==Path(os.environ['COCHEM_SOURCE_QUARANTINE_EVIDENCE']).resolve()
    assert active['revision']==os.environ['COCHEM_SOURCE_QUARANTINE_REVISION']
    assert not guard.loaded_origins(active)['escaped']
worker=runpy.run_path(str(source/'scripts/run_student_research.py'),run_name='actual_stdlib_worker_metadata_path')
assert Path(worker['_local_contract'].__code__.co_filename).resolve()==source/'scripts/run_student_research.py'
admission=worker['_local_contract']('student_actions_admission')
rest=worker['_local_contract']('student_actions_admission_git')
reader=worker['_local_contract']('student_actions_admission_git_readonly')
for module,name in ((admission,'student_actions_admission'),(rest,'student_actions_admission_git'),
                    (reader,'student_actions_admission_git_readonly')):
    assert Path(module.__file__).resolve()==source/'src/cochem_base/interfaces'/(name+'.py')
raw=expected_path.read_bytes()
assert hashlib.sha256(raw).hexdigest()==expected_hash
expected=admission.strict(raw)
repository,revision=expected['repository'],expected['revision']
deadline=time.time()+30
api=rest.ReadOnlyAPI(os.environ['GITHUB_TOKEN'],deadline=deadline,api_url=url,allow_loopback=True)
backend=None
report={'passed':False,'pid':os.getpid(),'records':[],
    'origins':{module.__name__:str(Path(module.__file__).resolve()) for module in (admission,rest,reader)}}
try:
    project=api._request('/repos/'+repository)
    assert project['id']==17 and project['full_name']==repository and project['private'] is True
    if expected['snapshot'] is not None:
        captured=expected['snapshot']
        run=api._request(f"/repos/{repository}/actions/runs/{captured['run_id']}")
        workflow=api._request(f"/repos/{repository}/actions/workflows/{run['workflow_id']}")
        assert workflow=={'id':123,'path':'.github/workflows/student_research.yml','state':'active'}
        admission.validate_run(run,captured['identity'])
    else:
        workflow=api._request(f'/repos/{repository}/actions/workflows/123')
        assert workflow['id']==123
    rest.qualify_capability(api,canonical_repository='ProfJJK-CoChem/CoChem-BASE',
        worker_sha=revision,repository=repository,source_sha=revision)
    report['numpy_loaded_before_lease']=any(name=='numpy' or name.startswith('numpy.') for name in sys.modules)
    report['inherited_thread_environment']={key:os.environ.get(key) for key in
        ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
    assert report['numpy_loaded_before_lease'] is False
    report['lease_entry_tasks']=sorted(int(path.name) for path in Path('/proc/self/task').iterdir())
    assert report['lease_entry_tasks']==[os.getpid()]
    with Path('/proc/self/stat').open('rb') as handle:
        owner_raw=handle.read(4097)
    owner_prefix,owner_separator,owner_tail=owner_raw.rpartition(b')')
    owner_fields=owner_tail.split()
    assert len(owner_raw)<=4096 and owner_separator and owner_prefix.split(b' ',1)[0]==str(os.getpid()).encode()
    assert len(owner_fields)>=20 and owner_fields[19].isdigit()
    report['independent_owner_identity']={'pid':os.getpid(),'start_ticks':owner_fields[19].decode('ascii')}
    backend=reader.ReadOnlyGitAdmissionBackend(api,repository,work_root=work_root,deadline=deadline,
        engineering_git_url=url+'/'+repository+'.git',allow_loopback=True)
    with backend:
        # Successful production acquisition performed the bounded strict PPID
        # inventory; unsupported/unreadable live stat never becomes empty.
        report['actual_lease_entry']=backend._lease.observation()
        assert report['actual_lease_entry']['owner_pid']==report['independent_owner_identity']['pid']
        assert report['actual_lease_entry']['owner_start_ticks']==report['independent_owner_identity']['start_ticks']
        assert report['actual_lease_entry']['entry_tasks']==[str(os.getpid())]
        assert report['actual_lease_entry']['entry_direct_children']==[]
        current=admission.AdmissionStore(backend).read()
        assert (current is None) is (expected['snapshot'] is None)
        if current is not None:
            assert current.tip==captured['tip']
            admission.require_expected(current,captured['identity'])
            assert backend.tip()==current.tip
            report['binding']=admission.verify_for_science(current,anchor=captured['anchor'],
                request_sha256=captured['identity']['payload_sha256'],run_id=captured['run_id'],run_attempt=1,
                **{key:captured['identity'][key] for key in ('repository_id','repository','workflow_id',
                    'branch','source_sha','worker_source_sha','request_id')})
    processes=[record for record in backend.diagnostics if 'pid' in record]
    assert processes and all(record['stopped'] for record in processes)
    report['passed']=True
except BaseException as error:
    report['error']=type(error).__name__+': '+str(error)
    raise
finally:
    report['records']=backend.diagnostics if backend is not None else []
    result_path.write_text(json.dumps(report,sort_keys=True,indent=2)+'\n')
"""


def cold_metadata_check(peer, tmp_path, snapshot, revision, barrier):
    """One actual child per cold barrier; no reader lease in threaded pytest."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    expected = {'repository': peer.repository, 'revision': revision, 'snapshot': None if snapshot is None else {
        'tip': snapshot.tip, 'identity': admission.identity(snapshot), 'anchor': snapshot.anchor,
        'run_id': snapshot.binding['run_id']}}
    expected_path = tmp_path/f'expected-{barrier}.json'
    expected_path.write_bytes(admission.canonical(expected))
    result_path = tmp_path/f'actual-{barrier}.json'
    paths, git = len(peer.paths), len(peer.gets)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
        PYTHONPATH=os.pathsep.join(source_paths(ROOT)), GITHUB_TOKEN=peer.token)
    child = None
    try:
        child = subprocess.run([sys.executable, '-B', '-c', COLD_CHILD, str(ROOT), str(expected_path),
            hashlib.sha256(expected_path.read_bytes()).hexdigest(), f'http://127.0.0.1:{peer.server_port}',
            str(tmp_path/f'barrier-{barrier}'), str(result_path)], env=environment,
            capture_output=True, text=True, timeout=45)
    finally:
        # Retain every completed child before any success assertion can fail.
        # The expected file contains engineering identity only, no credential.
        evidence = os.environ.get('ADMISSION_ENGINEERING_EVIDENCE')
        if evidence:
            destination = Path(evidence)
            destination.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(str(expected_path).encode()).hexdigest()[:20]
            output = '' if child is None else child.stdout+child.stderr
            record = {'scope': 'Actual source-guarded engineering metadata child, not hosted/scientific execution',
                'expected': expected, 'expected_sha256': hashlib.sha256(expected_path.read_bytes()).hexdigest(),
                'child_returncode': None if child is None else child.returncode,
                'completed_result': json.loads(result_path.read_bytes()) if result_path.exists() else None,
                'actual_GETs': actual_gets(peer, paths, git),
                'stdout': '' if child is None else child.stdout.replace(peer.token, '[loopback credential removed]'),
                'stderr': '' if child is None else child.stderr.replace(peer.token, '[loopback credential removed]'),
                'credential_redaction_applied': peer.token in output}
            (destination/f'cold-reader-{key}.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    assert peer.token not in child.stdout+child.stderr
    assert child.returncode == 0, child.stdout+child.stderr
    report = json.loads(result_path.read_bytes())
    assert report['passed'] is True and report['pid'] != os.getpid()
    assert all(Path(path).is_relative_to(ROOT) for path in report['origins'].values())
    counts = actual_gets(peer, paths, git)
    assert counts['capability'] == 2+2*len(admission.REQUIRED_PATHS) == 24
    assert counts['ledger_object'] == 0
    assert counts['project'] == counts['workflow'] == 1
    assert counts['run'] == int(snapshot is not None)
    assert counts['ref'] >= 2
    if snapshot is not None:
        assert report['binding']['run_id'] == snapshot.binding['run_id']
    return {'barrier': barrier, 'counts': counts, 'total': sum(counts.values()),
        'git_authenticated_requests': peer.git_authenticated, 'source_guarded_child': report,
        'child_returncode': child.returncode}


def retain(request, observations):
    destination = os.environ.get('ADMISSION_ENGINEERING_EVIDENCE')
    if destination:
        path = Path(destination)
        path.mkdir(parents=True, exist_ok=True)
        (path/(request.node.name+'-native-git-counts.json')).write_text(json.dumps({
            'scope': 'Actual local Git/smart-HTTP metadata counts, not hosted quotas or scientific execution',
            'counts_exclude': 'Earlier approval/project visibility, checkout/setup, wait retries, artifact upload and secondary limits',
            'source_sha256': {str(Path(module.__file__).relative_to(ROOT)): hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                for module in (admission, rest, reader)}, 'observations': observations}, sort_keys=True, indent=2)+'\n')


@pytest.mark.parametrize('completed_jobs', [0, 5, 20, 50])
def test_three_cold_git_readers_complete_histories_and_status_cost(project_approval_peer, tmp_path, request, completed_jobs):
    peer = project_approval_peer
    observations = []
    try:
        revision = _cache['_qualified_source'](peer, tmp_path)
        peer.revision = peer.setup_revision = revision
        # N completed requests plus one active bound request: 4*N+3 commits.
        snapshot = None
        for index in range(completed_jobs+1):
            snapshot = append_bound_job(peer, revision, index)
        for barrier in range(3):
            observations.append(cold_metadata_check(peer, tmp_path, snapshot, revision, barrier))
        assert len(observations) == 3
        assert len({item['source_guarded_child']['pid'] for item in observations}) == 3
        client = _contracts['project_approval_client'](peer, tmp_path)
        saved = client._saved_admission(snapshot)
        first_paths, first_git = len(peer.paths), len(peer.gets)
        assert client.status(saved)['run_id'] == snapshot.binding['run_id']
        cold_status = actual_gets(peer, first_paths, first_git)
        first_paths, first_git = len(peer.paths), len(peer.gets)
        assert client.status(saved)['run_id'] == snapshot.binding['run_id']
        warm_status = actual_gets(peer, first_paths, first_git)
        assert warm_status == {'capability': 0, 'project': 0, 'run': 1, 'workflow': 0, 'ref': 1, 'ledger_object': 0}
        observations.append({'completed_jobs': completed_jobs, 'ledger_commits': 4*completed_jobs+3,
            'three_cold_sum': sum(item['total'] for item in observations),
            'normal_client_cold_status': cold_status, 'normal_client_warm_status': warm_status})
        assert peer.submitted == []
        assert not any(path.endswith('/cancel') for path in peer.paths)
    finally:
        retain(request, observations)


def test_twenty_sequential_requests_one_project_three_fresh_checks_each(project_approval_peer, tmp_path, request):
    peer = project_approval_peer
    observations = []
    try:
        revision = _cache['_qualified_source'](peer, tmp_path)
        peer.revision = peer.setup_revision = revision
        for index in range(20):
            snapshot = append_bound_job(peer, revision, index)
            checks = [cold_metadata_check(peer, tmp_path/f'job-{index+1}', snapshot, revision, barrier)
                      for barrier in range(3)]
            observations.append({'job': index+1, 'commits': 4*(index+1)-1,
                'three_cold_checks': checks, 'total_metadata_gets': sum(item['total'] for item in checks)})
        total = sum(item['total_metadata_gets'] for item in observations)
        assert len(observations) == 20 and all(len(item['three_cold_checks']) == 3 for item in observations)
        # Primary 1000/hour is context, not a benchmark or acceptance threshold.
        observations.append({'twenty_sequential_one_project_total': total,
            'above_nominal_1000_workflow_token_hourly_primary_budget': total > 1000,
            'twenty_personal_projects': 'Separate repository token budgets; not a shared concurrency group',
            'actual_hosted_rate_acceptance': False})
        assert peer.submitted == []
    finally:
        retain(request, observations)
