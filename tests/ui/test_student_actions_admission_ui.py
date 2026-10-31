"""Actual widget/HTTP request ownership; no browser or scientific execution claim."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from ci_tools.source_quarantine import source_paths


@pytest.mark.parametrize('case', ['unbound_stop', 'stale_stop', 'held_render', 'recovery_busy', 'recovery_stale',
    'refresh_stale', 'prepared_review_submit', 'prepared_readonly_refresh', 'different_winner_context', 'review_basis_missing',
    'held_own_C', 'review_vpt2', 'review_torq_missing', 'review_xtb_na', 'review_composite_na', 'review_geometry_na', 'review_advanced_recipe'])
def test_project_request_widget_ownership_in_fresh_child(tmp_path, case):
    source = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(source_paths(source)),
        PYTHONDONTWRITEBYTECODE='1', COCHEM_CONFIG=str(tmp_path / 'absent-registry.json'),
        COCHEM_ARTIFACT_DIR=str(tmp_path / 'artifacts'), COCHEM_ARTIFACTS=str(tmp_path / 'artifacts'),
        COCHEM_STUDENT_AUTO_SETUP='false', COCHEM_STUDENT_AUTO_REMOTE_CHECK='0')
    result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), case, str(tmp_path)],
        env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def _exercise(case, root):
    import runpy
    import threading
    import time
    import json
    import socket

    source = Path(__file__).resolve().parents[2]
    if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
        startup = sys.modules.get('sitecustomize')
        assert startup is not None and Path(startup.__file__).resolve() == source / 'ci_tools/quarantine_startup/sitecustomize.py'
        state = getattr(sys.modules.get('ci_tools.source_quarantine'), '_active', None)
        assert state is not None and state['copied'] == source
    from ui.voila_layout.cochem_gui import CoChemGUI
    import ui.voila_layout.cochem_gui as gui_module
    from cochem_base.interfaces import student_actions_admission as admission
    from cochem_base.interfaces import student_actions_admission_git as transport
    assert Path(gui_module.__file__).resolve() == source / 'ui/voila_layout/cochem_gui.py'
    assert Path(admission.__file__).resolve() == source / 'src/cochem_base/interfaces/student_actions_admission.py'
    assert Path(transport.__file__).resolve() == source / 'src/cochem_base/interfaces/student_actions_admission_git.py'
    fixtures = runpy.run_path(str(source / 'tests/base/test_student_actions_contract.py'), run_name='widget_http_fixture')
    class DropAcceptedDispatchAck(fixtures['ProjectApprovalHandler']):
        def answer(self,payload,status=200):
            if (getattr(self.server,'drop_research_dispatch_ack',False)
                    and self.path==f'/repos/{self.server.repository}/actions/workflows/123/dispatches'):
                self.server.drop_research_dispatch_ack=False
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            return super().answer(payload,status)
    peer = fixtures['ProjectApprovalServer']()
    # Configure the actual loopback HTTP server before it serves any requests.
    # The accepted dispatch side effect runs in the original handler; only its
    # real transport acknowledgement can be dropped. No production seam is patched.
    peer.RequestHandlerClass=DropAcceptedDispatchAck
    thread = threading.Thread(target=peer.serve_forever, daemon=True)
    thread.start()
    try:
        from cochem_base.interfaces.student_actions import StudentActionsClient
        client = StudentActionsClient(peer.repository, branch='main', token=peer.token,
            repository_root=root/'source', artifact_dir=root/'artifacts',
            api_url=f'http://127.0.0.1:{peer.server_port}', allow_loopback=True)
        store = admission.AdmissionStore(transport.GitAdmissionBackend(client, peer.repository))
        request = fixtures['_request']()
        request.update(repository=peer.repository, source_sha=peer.setup_revision, worker_source_sha=peer.revision)
        request['calculation'].update(charge=0,multiplicity=1,is_opt=True,is_freq=False,is_vpt2=False)
        if case in {'review_basis_missing','review_vpt2','review_composite_na','review_advanced_recipe'}:
            request['calculation'].update(engine='orca',method='HF',basis_set='STO-3G')
            if case=='review_basis_missing':request['calculation'].pop('basis_set')
            if case=='review_vpt2':request['calculation'].update(is_vpt2=True,is_freq=True)
            if case in {'review_composite_na','review_advanced_recipe'}:
                request['calculation'].update(method='r2SCAN-3c',basis_set=None)
            if case=='review_advanced_recipe':request['calculation'].update(recipe='R1',grid_stage=3,is_freq=True)
        if case in {'review_torq_missing','review_geometry_na'}:
            import base64,hashlib
            raw=request['calculation']['geometry'].encode()
            name='inputs/source&review.xyz'
            request['files']={name:{'content_base64':base64.b64encode(raw).decode(),'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw)}}
            request['calculation']=None
            request['provider']={'schema_version':'cochem.student-provider/1','module':'torq',
                'operation':'research_scan' if case=='review_torq_missing' else 'geometry_analysis',
                'artifact':name,'artifact_sha256':hashlib.sha256(raw).hexdigest(),
                'options':{'cores':1,'memory_mb':512} if case=='review_torq_missing' else {}}
        first = store.prepare(admission.canonical(request), repository_id=17, branch='main', workflow_id=123)
        prepared_cases={'stale_stop','refresh_stale','prepared_review_submit','prepared_readonly_refresh','different_winner_context','held_own_C'}
        if case not in prepared_cases and not case.startswith('review_'):
            store.resume(admission.identity(first)).publish()
        recovered = client.recover_admission()
        assert recovered['request_id'] == request['request_id'] and recovered['admission_terminal'] is False
        gui = CoChemGUI()
        # Constructor catalog work is real asynchronous filesystem work. Wait
        # for those actual owned threads; never clear its busy flag or weaken
        # the production guard to make a recovery click run early.
        def catalog_state():
            with gui._local_file_workers_lock:
                workers=tuple(gui._local_file_workers)
            return {'busy':gui._local_file_operation is not None,
                'threads':[{'name':worker.name,'ident':worker.ident,'native_id':worker.native_id,
                            'alive':worker.is_alive()} for worker in workers]}
        started=time.monotonic();catalog_witness={'initial':catalog_state()}
        deadline=started+10
        try:
            while gui._local_file_operation is not None or gui._local_file_work_active():
                remaining=deadline-time.monotonic()
                assert remaining>0,'The actual startup file catalog did not finish within its bound'
                with gui._local_file_workers_lock:
                    workers=tuple(gui._local_file_workers)
                for worker in workers:
                    if worker.ident is not None:
                        worker.join(timeout=min(1,max(0,deadline-time.monotonic())))
                if gui._local_file_operation is not None:
                    time.sleep(min(.01,max(0,deadline-time.monotonic())))
            assert gui._local_file_operation is None and not gui._local_file_work_active()
        finally:
            catalog_witness.update(final=catalog_state(),elapsed_seconds=time.monotonic()-started,
                scope='Actual constructor file-catalog readiness only; no historical state reconstruction or native job')
            evidence=os.environ.get('ADMISSION_ENGINEERING_EVIDENCE')
            if evidence:
                destination=Path(evidence);destination.mkdir(parents=True,exist_ok=True)
                (destination/f'widget-startup-catalog-{case}.json').write_text(json.dumps(catalog_witness,sort_keys=True,indent=2)+'\n')
        gui.gh_repo_input.value = peer.repository
        gui.gh_branch_input.value = 'main'
        gui.calc_env_dropdown.value = 'github-actions'
        before = (gui.matrix_geometry.value, gui.state.__dict__.copy())
        def join(worker):
            worker.join(timeout=25)
            assert not worker.is_alive()
        def block_ref():
            peer.blocked_route=f'/repos/{peer.repository}/git/ref/heads/cochem-student-admission-v1'
            peer.blocked_entered.clear();peer.blocked_release.clear()
        if case in {'recovery_busy','recovery_stale','prepared_review_submit','prepared_readonly_refresh','different_winner_context','held_own_C'} or case.startswith('review_'):
            gui._actions_client=client
            if case in {'different_winner_context','held_own_C'}:
                store.stop(admission.identity(first))
            if case=='recovery_stale':
                original_context=gui._new_remote_stop('actions')
            if case.startswith('recovery_'):
                block_ref()
            gui.btn_actions_recover.click()
            if case.startswith('recovery_'):
                assert peer.blocked_entered.wait(timeout=5)
                assert gui._actions_admission_checking and gui._actions_state_operation is not None
                assert gui.btn_execute.disabled
                old_hpc_serial=gui._hpc_job_serial
                gui._execute_pipeline(None);gui._submit_student_hpc();gui._open_student_hpc_history();gui._retrieve_student_actions()
                assert gui._hpc_job_serial==old_hpc_serial and gui._hpc_submission is None
                if case=='recovery_stale':
                    replacement=gui._new_remote_stop('actions')
                    assert replacement is not original_context and replacement==original_context
                    gui.actions_status.value='<p>New selection retained</p>'
                peer.blocked_release.set()
            join(gui._actions_recovery_worker)
            if case=='recovery_stale':
                assert gui._actions_submission is None
                assert gui._remote_stops['actions'] is replacement
                assert gui.actions_status.value=='<p>New selection retained</p>'
                assert gui._actions_state_operation is None and not gui.btn_actions_recover.disabled
                gui.btn_actions_recover.click();join(gui._actions_recovery_worker)
                assert gui._actions_submission['request_id']==request['request_id']
                assert gui._actions_running and gui._actions_state_operation is None
            elif case=='recovery_busy':
                assert gui._actions_running and gui._actions_submission['request_id']==request['request_id']
                assert gui._actions_state_operation is None
            elif case.startswith('review_'):
                held=case in {'review_basis_missing','review_vpt2','review_torq_missing'}
                assert gui.btn_actions_refresh.description=='Submit saved calculation'
                assert gui.btn_actions_refresh.disabled is held
                if held:
                    before_tip=store.read().tip
                    gui.btn_actions_refresh.click()
                    assert not peer.submitted and store.read().tip==before_tip
                    assert 'cannot be submitted' in gui.actions_status.value or 'instructor review' in gui.actions_status.value
                else:
                    assert 'Review the saved calculation' in gui.actions_status.value
                    assert 'not your current draft edits' in gui.actions_status.value
                    from html.parser import HTMLParser
                    class ReviewText(HTMLParser):
                        def __init__(self):super().__init__();self.depth=0;self.visible=[];self.advanced=[]
                        def handle_starttag(self,tag,attrs):
                            if tag=='details':self.depth+=1
                        def handle_endtag(self,tag):
                            if tag=='details':self.depth-=1
                        def handle_data(self,text):
                            (self.advanced if self.depth else self.visible).append(text)
                    parsed=ReviewText();parsed.feed(gui.actions_status.value)
                    visible,advanced=' '.join(parsed.visible),' '.join(parsed.advanced)
                    assert '<details><summary>Advanced saved settings and provenance</summary>' in gui.actions_status.value
                    assert request['request_id'] not in visible and recovered['payload_sha256'] not in visible
                    assert request['request_id'] in advanced and recovered['payload_sha256'] in advanced
                    assert 'Saved at' in visible and 'Saved task' in visible
                    assert 'Input file' in visible or 'Input structure' in visible
                    if case=='review_advanced_recipe':
                        assert 'Additional solvent, constraint or other options' in visible
                        assert 'R1' in advanced and 'R1' not in visible
                    if case=='review_xtb_na':assert 'Not applicable' in gui.actions_status.value
                    if case=='review_composite_na':assert 'Built into' in gui.actions_status.value
                    if case=='review_geometry_na':
                        assert 'Not applicable' in gui.actions_status.value and 'source&amp;review.xyz' in gui.actions_status.value
                    if case=='review_advanced_recipe':
                        assert 'Geometry optimization and harmonic frequencies' in gui.actions_status.value
                        assert 'Saved recipe' in gui.actions_status.value and 'R1' in gui.actions_status.value
                assert not peer.submitted
            elif case=='held_own_C':
                assert gui._actions_admission_checked==(peer.repository,'main')
                peer.drop_research_dispatch_ack=True
                gui.matrix_engine.value='XTB';gui.xtb_task.value='optimization'
                gui.matrix_geometry.value=request['calculation']['geometry']
                gui._submit_student_actions();join(gui._actions_worker)
                own=store.read()
                assert own.state['phase']=='dispatch_intent' and own.binding is None
                assert len(peer.submitted)==1 and own.intent['request_id']==peer.submitted[0]['request_id']
                assert gui._actions_submission['request_id']==own.intent['request_id']
                assert gui._actions_running and not gui.btn_actions_refresh.disabled
                assert gui.btn_actions_refresh.description=='Refresh calculation status'
                assert 'needs attention' in gui.actions_status.value
                original_hash=own.intent['payload_sha256']
                gui.btn_actions_refresh.click();join(gui._actions_refresh_worker)
                bound=store.read()
                assert bound.state['phase']=='bound' and bound.binding['run_id']==peer.runs[0]['id']
                assert bound.intent['payload_sha256']==original_hash
                assert len(peer.submitted)==1
                assert gui.btn_actions_refresh.description=='Refresh calculation status'
                assert not gui.btn_actions_refresh.disabled
                assert not any('/cancel' in path for path in peer.paths)
                return
            elif case=='different_winner_context':
                assert gui._actions_admission_checked==(peer.repository,'main')
                competing=dict(request,request_id='ac72d7ea-3c83-425e-9163-e5d5b15d0af2')
                winner=store.prepare(admission.canonical(competing),repository_id=17,branch='main',workflow_id=123)
                gui.matrix_engine.value='XTB';gui.xtb_task.value='optimization'
                gui.matrix_geometry.value=request['calculation']['geometry']
                block_ref();gui._submit_student_actions()
                assert peer.blocked_entered.wait(timeout=5)
                old_context=gui._remote_stops['actions']
                # Genuine RLock/worker-stack boundary: do not fabricate a UI callback queue.
                with gui._job_stop_lock:
                    peer.blocked_release.set();deadline=time.monotonic()+3;witness=False
                    while time.monotonic()<deadline:
                        frame=sys._current_frames().get(gui._actions_worker.ident)
                        while frame is not None:
                            if frame.f_code.co_name=='failure' and Path(frame.f_code.co_filename).resolve()==source/'ui/voila_layout/cochem_gui.py':
                                witness=True;break
                            frame=frame.f_back
                        if witness:break
                        time.sleep(.005)
                    assert witness,'No actual guarded failure-publication boundary was observed'
                    assert gui._actions_submission is None
                    gui.guided_cancel.click()
                    assert old_context['requested'] is True
                join(gui._actions_worker)
                assert gui._actions_submission['request_id']==competing['request_id']
                assert gui._remote_stops['actions'] is not old_context
                assert gui._remote_stops['actions']['requested'] is False
                assert store.read().tip==winner.tip and not store.read().state['stop_requested']
                assert gui.btn_actions_refresh.description=='Submit saved calculation'
                assert not gui.btn_actions_refresh.disabled
                assert 'Review the saved calculation' in gui.actions_status.value
                assert 'not your current draft edits' in gui.actions_status.value
                assert competing['request_id'] in gui.actions_status.value
            else:
                assert gui.btn_actions_refresh.description=='Submit saved calculation'
                assert not gui.btn_actions_refresh.disabled
                assert 'not your current draft edits' in gui.actions_status.value
                assert request['request_id'] in gui.actions_status.value
                original=request['calculation']['geometry']
                gui.matrix_geometry.value='2\nEdited current draft; not the saved request\nH 0 0 0\nH 0 0 0.8\n'
                if case=='prepared_review_submit':
                    gui.btn_actions_refresh.click();join(gui._actions_refresh_worker)
                    assert len(peer.submitted)==1
                    assert peer.submitted[0]['calculation']['geometry']==original
                    assert peer.submitted[0]['calculation']['charge']==0 and peer.submitted[0]['calculation']['multiplicity']==1
                    assert gui.matrix_geometry.value != original
                    assert gui.btn_actions_refresh.description=='Refresh calculation status'
                else:
                    gui._refresh_student_actions();join(gui._actions_refresh_worker)
                    assert not peer.submitted and store.read().state['phase']=='prepared'
            assert not any('/cancel' in path for path in peer.paths)
            if case!='prepared_review_submit':assert not peer.submitted
            return
        assert gui._actions_admission_checked is None
        assert gui.btn_execute.disabled
        # Render an actual project-backed observation through the production GUI.
        # The separate client controls exercise discovery; this is not the recovery closure/browser lane.
        gui._actions_client, gui._actions_submission = client, dict(recovered)
        gui._render_student_actions_status(recovered)
        assert gui._actions_running and not gui.btn_cancel.disabled
        assert gui.btn_execute.disabled
        assert gui.matrix_geometry.value == before[0]
        assert not peer.submitted
        if case == 'refresh_stale':
            block_ref();gui._refresh_student_actions()
            assert peer.blocked_entered.wait(timeout=5)
            # Actual same-project Git history moves A→withdrawn→B while A's GET is delayed.
            local=fixtures['AdmissionGitStore'](peer.store.path)
            local.stop(admission.identity(first))
            competing=dict(request,request_id='ac72d7ea-3c83-425e-9163-e5d5b15d0af2')
            second=local.prepare(admission.canonical(competing),repository_id=17,branch='main',workflow_id=123)
            observed=client._saved_admission(second)
            replacement=gui._new_remote_stop('actions')
            gui._actions_client,gui._actions_submission=client,observed
            gui._render_student_actions_status(observed)
            current_markup=gui.actions_status.value
            peer.blocked_release.set();join(gui._actions_refresh_worker)
            assert gui._actions_submission['request_id']==competing['request_id']
            assert gui._remote_stops['actions'] is replacement and not replacement['requested']
            assert gui.actions_status.value==current_markup
            assert local.read().tip==second.tip and not local.read().state['stop_requested']
            assert not peer.submitted
            return
        if case == 'held_render':
            assert 'remains active' in gui.actions_status.value
            assert gui.btn_actions_retrieve.disabled
            assert gui.btn_actions_refresh.description == 'Refresh calculation status'
            return
        if case == 'stale_stop':
            store.stop(admission.identity(first))
            second_request = dict(request, request_id='ac72d7ea-3c83-425e-9163-e5d5b15d0af2')
            second = store.prepare(admission.canonical(second_request), repository_id=17, branch='main', workflow_id=123)
            before_tip = second.tip
        gui.btn_cancel.click()
        context = gui._remote_stops['actions']
        worker = context.get('worker')
        assert worker is not None
        worker.join(timeout=20)
        assert not worker.is_alive()
        observed = store.read()
        if case == 'stale_stop':
            assert observed.tip == before_tip and observed.state['stop_requested'] is False
            assert observed.intent['request_id'] == second_request['request_id']
            assert context['retry_required'] is True
        else:
            assert observed.intent['request_id'] == request['request_id']
            assert observed.state['stop_requested'] is True and observed.binding is None
            assert context['requested'] is True
        assert not peer.submitted
        assert not any('/cancel' in path for path in peer.paths)
        assert gui.matrix_geometry.value == before[0]
    finally:
        peer.shutdown()
        peer.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()
        peer._git_fixture.cleanup()


if __name__ == '__main__':
    _exercise(sys.argv[1], Path(sys.argv[2]))
