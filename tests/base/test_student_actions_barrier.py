"""Real HTTP/filesystem barrier controls; markers are not scientific results."""
from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import time

import pytest

from ci_tools.source_quarantine import source_paths
from cochem_base.interfaces import student_actions_admission as admission
from cochem_base.interfaces import student_actions_admission_git as transport
from cochem_base.interfaces.student_request import canonical_json, encode_request

ROOT = Path(__file__).resolve().parents[2]
_fixtures = runpy.run_path(str(Path(__file__).with_name('test_student_actions_contract.py')),
                         run_name='barrier_engineering_fixture')
project_approval_peer = _fixtures['project_approval_peer']


CHILD = r'''
import json,os,runpy,sys
from pathlib import Path
source,output,url,marker=sys.argv[1:]
source,output,marker=Path(source),Path(output),Path(marker)
if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
    startup=sys.modules.get('sitecustomize')
    assert startup is not None and Path(startup.__file__).resolve()==source/'ci_tools/quarantine_startup/sitecustomize.py'
    state=getattr(sys.modules.get('ci_tools.source_quarantine'),'_active',None)
    assert state is not None and state['copied']==source
module=runpy.run_path(str(source/'scripts/run_student_research.py'))
assert Path(module['verify_admission'].__code__.co_filename).resolve()==source/'scripts/run_student_research.py'
module['preflight'](output)
module['approve_worker'](output,api_url=str(url),allow_loopback=True)
receipt=module['verify_admission'](output,wait=os.environ['ENGINEERING_WAIT']=='1',api_url=str(url),allow_loopback=True,
    engineering_git_url=str(url)+'/'+os.environ['GITHUB_REPOSITORY']+'.git')
result=module['contract'].strict_json((output/'student-result.json').read_bytes())
assert result['operation_performed'] is False and result['status']=='prepared'
marker.write_bytes(module['contract'].canonical_json({'engineering_guard_only':True,**receipt}))
'''


@pytest.mark.parametrize('case', ['valid', 'old_start_nowait', 'missing_anchor', 'attempt2', 'stop', 'unbound',
                                 'expired', 'metadata403', 'missing_workflow', 'wrong_repository'])
def test_exact_workflow_barrier_in_fresh_source_child(project_approval_peer, tmp_path, case):
    peer = project_approval_peer
    peer.revision = subprocess.run(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
        capture_output=True, text=True, timeout=10, check=True).stdout.strip()
    peer.variables['COCHEM_APPROVED_BASE_SHA'] = peer.revision
    client = _fixtures['project_approval_client'](peer, tmp_path)
    request = _fixtures['_request']()
    request.update(repository=peer.repository, source_sha=peer.setup_revision,
                   worker_source_sha=peer.revision)
    encoded, digest = encode_request(request)
    store = admission.AdmissionStore(transport.GitAdmissionBackend(client, peer.repository))
    prepared = store.prepare(canonical_json(request), repository_id=17, branch='main', workflow_id=123)
    owner = store.resume(admission.identity(prepared)).publish()
    owner.post(transport.ActionsAdmissionTransport(client))
    snapshot = store.read()
    if case != 'unbound':
        snapshot = store.bind(transport.ActionsAdmissionTransport(client), admission.identity(snapshot))
    if case == 'stop':
        store.stop(admission.identity(snapshot))
    if case == 'metadata403':
        peer.admission_metadata_status = 403
    if case == 'missing_workflow':
        peer.admission_run_changes = {'workflow_id': None}
    if case == 'wrong_repository':
        peer.admission_project_id = 18
    marker, output = tmp_path / 'engineering-protected-marker.json', tmp_path / 'evidence'
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
        PYTHONPATH=os.pathsep.join(source_paths(ROOT)), REQUEST_BASE64=encoded, REQUEST_SHA256=digest,
        REQUEST_ID=request['request_id'], REQUEST_ADMISSION_ANCHOR='' if case == 'missing_anchor' else snapshot.anchor,
        GITHUB_REPOSITORY=peer.repository, GITHUB_REPOSITORY_ID='17', GITHUB_SHA=peer.setup_revision,
        GITHUB_REF='refs/heads/main', DEFAULT_BRANCH='main', GITHUB_EVENT_NAME='workflow_dispatch',
        GITHUB_RUN_ID=str(peer.runs[0]['id']), GITHUB_RUN_ATTEMPT='2' if case == 'attempt2' else '1',
        GITHUB_TOKEN=peer.token, COCHEM_APPROVED_BASE_SHA=peer.revision, COCHEM_COURSE_CHANNEL='',
        COCHEM_ADMISSION_JOB_STARTED_EPOCH=str(int(time.time()) - (241 if case == 'expired' else 600 if case == 'old_start_nowait' else 0)),
        ENGINEERING_WAIT='1' if case == 'expired' else '0')
    tip_before_child = store.read().tip
    result = subprocess.run([sys.executable, '-B', '-c', CHILD, str(ROOT), str(output),
        f'http://127.0.0.1:{peer.server_port}', str(marker)], env=environment,
        capture_output=True, text=True, timeout=45)
    assert peer.token not in result.stdout + result.stderr
    assert (result.returncode == 0) is (case in {'valid', 'old_start_nowait'}), result.stdout + result.stderr
    assert marker.exists() is (case in {'valid', 'old_start_nowait'})
    report = json.loads((output / 'student-result.json').read_bytes())
    assert report['operation_performed'] is False and report['status'] == 'prepared'
    assert len(peer.submitted) == 1
    assert all(row['body'].get('force') is False for row in peer.git_writes if row['method'] == 'PATCH')
    # The barrier is read-only: no child adds a ledger transition or second POST.
    assert store.read().tip == tip_before_child
    if case == 'stop':
        assert store.read().state['stop_requested'] is True
