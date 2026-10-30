"""Real owned-process/UI cancellation controls; no synthetic chemistry results."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from ci_tools.source_quarantine import source_paths


@pytest.mark.parametrize('case', ['fanout', 'topos_unknown', 'individual', 'pending_http',
    'failed_http', 'stale_http', 'wrong_http', 'terminal_http', 'retry_http', 'probe_http', 'busy_guards', 'geometry_precancel',
    'hpc_timeout', 'hpc_history', 'caption_preservation', 'hpc_unknown', 'hpc_unknown_corrupt', 'hpc_unknown_history', 'hpc_stale_history'])
def test_active_work_in_fresh_process(tmp_path, case):
    source = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(source_paths(source)),
        PYTHONDONTWRITEBYTECODE='1', COCHEM_CONFIG=str(tmp_path / 'absent-registry.json'),
        COCHEM_ARTIFACT_DIR=str(tmp_path / 'artifacts'), COCHEM_ARTIFACTS=str(tmp_path / 'artifacts'),
        COCHEM_STUDENT_AUTO_SETUP='false', COCHEM_STUDENT_AUTO_REMOTE_CHECK='0')
    result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), case, str(tmp_path)],
                            env=environment, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr


def _exercise(case, root):
    source = Path(__file__).resolve().parents[2]
    if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
        startup = sys.modules.get('sitecustomize')
        assert startup is not None
        assert Path(startup.__file__).resolve() == source / 'ci_tools/quarantine_startup/sitecustomize.py'
        state = getattr(sys.modules.get('ci_tools.source_quarantine'), '_active', None)
        assert state is not None and state['copied'] == source
    import threading
    import time

    from cochem_base.interfaces.module_execution import ModuleOperationCancelled, _run_adapter
    from cochem_base.topos_runner import TOPOSExecutionBroker, _write_json
    from ui.voila_layout.cochem_gui import CoChemGUI
    import ui.voila_layout.cochem_gui as gui_module
    import cochem_base.interfaces.module_execution as module_execution
    import cochem_base.topos_runner as topos_runner
    assert Path(gui_module.__file__).resolve() == source / 'ui/voila_layout/cochem_gui.py'
    assert Path(module_execution.__file__).resolve() == source / 'src/cochem_base/interfaces/module_execution.py'
    assert Path(topos_runner.__file__).resolve() == source / 'src/cochem_base/topos_runner.py'

    gui = CoChemGUI()
    if case in {'hpc_timeout', 'hpc_history', 'hpc_unknown', 'hpc_unknown_corrupt', 'hpc_unknown_history', 'hpc_stale_history'}:
        return _hpc_review_case(gui, root, case)
    if case.endswith('_http'):
        return _http_case(gui, root, case)
    if case == 'caption_preservation':
        original_widget = gui.calculation_result
        original_value = original_widget.value
        original_status = gui.state.system_status
        original_input = gui.matrix_geometry.value
        assert 'No tables or diagrams have been collected here yet.' in gui.research_report_output.value
        assert 'No calculation results yet' not in gui.research_report_output.value
        gui.guided_step_buttons['modules'].click()
        def walk(widget):
            yield widget
            for child in getattr(widget, 'children', ()):
                yield from walk(child)
        assert original_widget in tuple(walk(gui.view_modules))
        assert gui.calculation_result is original_widget and original_widget.value == original_value
        assert gui.state.system_status == original_status and gui.matrix_geometry.value == original_input
        assert gui.research_isomer_choices.options == () and gui.btn_research_compare.disabled
        # This checks widget preservation only. It creates no native result or
        # accepted-science status; a real native browser observation is separate.
        return
    if case == 'geometry_precancel':
        import hashlib
        from cochem_base.interfaces.artifact_handoff import load_module_handoff
        source = root / 'original-water.xyz'
        raw = b'3\nOriginal geometry, no energy observation\nO 0 0 0\nH .757 .587 0\nH -.757 .587 0\n'
        source.write_bytes(raw)
        gui.calc_env_dropdown.value = 'local'
        gui.module_recipient.value = 'torq'
        gui.module_artifact.value = str(source)
        gui.module_output.value = str(root / 'handoffs')
        gui.module_root.value = str(root / 'absent-modules')
        previous = gui._last_module_result = object()  # Opaque UI selection marker, not a result report.
        installer = getattr(gui, '_module_worker', None)
        entered, release = threading.Event(), threading.Event()
        gated = {'done': False}
        def pause_real_original_read(event, arguments):
            if event != 'open' or gated['done']:
                return
            try:
                target = Path(os.fsdecode(arguments[0]))
            except (TypeError, ValueError):
                return
            if target == source and threading.current_thread() is getattr(gui, '_module_geometry_worker', None):
                gated['done'] = True
                entered.set()
                assert release.wait(10)
        # Child-only real I/O scheduling boundary, not a replacement parser,
        # execution function or downstream engine. No installation is required.
        sys.addaudithook(pause_real_original_read)
        try:
            gui._run_module_geometry()
            assert entered.wait(10) and gui._pipeline_running
            assert not gui.guided_cancel.disabled
            gui.guided_cancel.click()
            assert gui._pipeline_cancellation.is_set()
            release.set()
            gui._module_geometry_worker.join(15)
            assert not gui._module_geometry_worker.is_alive() and not gui._pipeline_running
            assert 'Geometry analysis cancelled' in gui.module_handoff_status.value
            assert gui._last_module_result is previous and getattr(gui, '_module_worker', None) is installer
            assert source.read_bytes() == raw
            handoffs = list((root / 'handoffs').glob('execution_*/handoff/handoff.json'))
            assert len(handoffs) == 1
            handoff = load_module_handoff(handoffs[0])
            assert handoff.artifact.sha256 == hashlib.sha256(raw).hexdigest()
            assert not list((root / 'handoffs').glob('execution_*/result/result.json'))
        finally:
            release.set()
            if hasattr(gui, '_module_geometry_worker'):
                gui._module_geometry_worker.join(15)
        return
    if case == 'busy_guards':
        gui.calc_env_dropdown.value = 'local'
        gui._actions_running = True
        before = gui.matrix_geometry.value
        for environment in ('local', 'github-actions'):
            gui.calc_env_dropdown.value = environment
            gui._run_module_geometry()
            assert 'Wait for or cancel' in gui.module_handoff_status.value
            assert not hasattr(gui, '_module_geometry_worker')
        gui.calc_env_dropdown.value = 'local'
        gui._execute_periodic_pipeline()
        assert 'Wait for the active operation' in gui.state.error_message
        assert not gui._pipeline_running and not hasattr(gui, '_pipeline_worker')
        gui._start_topos_search()
        assert 'Wait for the active operation' in gui.topos_status.value
        assert not gui._topos_running and gui.matrix_geometry.value == before
        gui._refresh_execution_gate()
        assert gui.btn_periodic_run.disabled
        gui._actions_running = False
        return
    if case == 'individual':
        gui._pipeline_running = gui._topos_running = True
        gui._refresh_running_jobs()
        assert not gui.guided_cancel.disabled
        gui.btn_topos_cancel.disabled = False
        gui.btn_topos_cancel.click()
        assert gui._topos_cancellation.is_set() and not gui._pipeline_cancellation.is_set()
        gui._topos_running = False
        gui._refresh_running_jobs()
        assert not gui.guided_cancel.disabled
        gui.btn_cancel.disabled = True
        assert not gui.guided_cancel.disabled
        gui._pipeline_running = False
        gui._refresh_running_jobs()
        assert gui.guided_cancel.disabled
        return
    broker = TOPOSExecutionBroker(root / 'scratch', root / 'store')
    job = 'topos_job_' + 'a' * 32
    folder = broker.scratch_root / job
    folder.mkdir()
    _write_json(folder / 'telemetry.json', {'job_id': job, 'status': 'RUNNING', 'error': None,
        'candidates_found': 0, 'deduplicated_count': 0, 'lowest_energy_hartree': None})
    # Explicit engineering processes bound to real cancellation APIs. These
    # processes do not impersonate CREST or produce a scientific result.
    owned = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(30)'])
    unrelated = subprocess.Popen([sys.executable, '-B', '-c', 'import time; time.sleep(30)'])
    broker.active_processes[job] = owned
    gui._topos_broker, gui._topos_job_id = broker, job
    gui._topos_running = True
    gui._pipeline_running = True
    gui.btn_cancel.disabled = False
    witness = root / 'adapter.pid'
    command = [sys.executable, '-B', '-c',
        'import os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)', str(witness)]
    observed = []
    def adapter():
        try:
            with (root / 'adapter.log').open('w') as log:
                _run_adapter(command, root, log, 30, cancel_event=gui._pipeline_cancellation)
        except ModuleOperationCancelled:
            observed.append('cancelled')
        finally:
            gui._pipeline_running = False
    thread = threading.Thread(target=adapter)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not witness.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert witness.is_file() and owned.poll() is None and unrelated.poll() is None
        if case == 'topos_unknown':
            # Real retained-metadata failure prevents broker cancellation; the
            # running owned handle must stay tracked, then be safely retryable.
            telemetry = folder / 'telemetry.json'
            retained = telemetry.read_bytes()
            telemetry.unlink()
            gui._poll_topos_search()
            assert gui._topos_running and gui._topos_attention
            assert owned.poll() is None and not gui.guided_cancel.disabled
            assert 'could not be confirmed' in gui.topos_status.value
            telemetry.write_bytes(retained)
            gui._topos_worker = threading.Thread()  # already-finished monitor generation
        gui.guided_cancel.click()
        assert gui._pipeline_cancellation.is_set()
        assert gui._topos_cancellation.is_set(), 'Header missed the active owned TOPOS job'
        # The real TOPOS polling worker owns the blocking broker operation.
        if case != 'topos_unknown':
            gui._topos_worker = threading.Thread(target=gui._poll_topos_search)
            gui._topos_worker.start()
        thread.join(15)
        gui._topos_worker.join(15)
        assert not thread.is_alive() and observed == ['cancelled']
        assert not gui._topos_worker.is_alive() and owned.poll() is not None
        assert broker.poll_telemetry(job)['status'] == 'CANCELLED'
        assert unrelated.poll() is None
        assert not list(broker.store_root.iterdir())
    finally:
        gui._pipeline_cancellation.set()
        thread.join(15)
        if owned.poll() is None:
            broker.cancel_search(job)
        if hasattr(gui, '_topos_worker'):
            gui._topos_worker.join(15)
        unrelated.terminate()
        unrelated.wait(timeout=10)
        gui._topos_running = False


def _http_case(gui, root, case):
    from collections import Counter
    from datetime import datetime, timezone
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import json
    import secrets
    import threading
    import uuid

    from cochem_base.interfaces.student_actions import RUN_PREFIX, StudentActionsClient
    import cochem_base.interfaces.student_actions as student_actions
    assert Path(student_actions.__file__).resolve() == Path(__file__).resolve().parents[2] / 'src/cochem_base/interfaces/student_actions.py'

    token = secrets.token_urlsafe(32)
    request_id = str(uuid.uuid4())
    state = {'registered': case != 'pending_http', 'posts': [], 'gets': [],
             'access_log': [], 'responses': [],
             'entered': threading.Event(), 'release': threading.Event(),
             'status_error': case == 'probe_http', 'terminal': False}
    submission = {'request_id': request_id, 'repository': 'student/project', 'branch': 'main',
        'source_sha': 'a' * 40, 'worker_source_sha': 'b' * 40, 'payload_sha256': 'c' * 64,
        'workflow_id': 41, 'submitted_at': datetime.now(timezone.utc).isoformat(),
        'run_id': None if case == 'pending_http' else 123, 'run_attempt': 1, 'status': 'queued'}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            state['access_log'].append(format % args)
        def answer(self, status, value):
            raw = json.dumps(value).encode()
            state['responses'].append((self.requestline, status))
            self.send_response(status)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(raw)
        def do_GET(self):
            assert self.headers['Authorization'] == 'Bearer ' + token
            state['gets'].append(self.path)
            if state['status_error']:
                self.answer(503, {'message': 'Deliberate real protocol failure'})
                return
            run = {'id': 123, 'display_title': RUN_PREFIX + request_id,
                'event': 'workflow_dispatch', 'head_sha': '0' * 40 if case == 'wrong_http' else 'a' * 40,
                'workflow_id': 41, 'head_branch': 'main', 'run_attempt': 1,
                'status': 'completed' if case == 'terminal_http' or state['terminal'] else 'in_progress',
                'conclusion': 'success' if case == 'terminal_http' else None,
                'html_url': 'https://github.com/student/project/actions/runs/123'}
            if self.path.startswith('/repos/student/project/actions/workflows/41/runs?'):
                self.answer(200, {'workflow_runs': [run] if state['registered'] else []})
            elif self.path == '/repos/student/project/actions/runs/123':
                self.answer(200, run)
            else:
                self.answer(404, {'message': 'Unexpected test protocol route'})
        def do_POST(self):
            assert self.headers['Authorization'] == 'Bearer ' + token
            state['posts'].append(self.path)
            assert self.path == '/repos/student/project/actions/runs/123/cancel'
            state['entered'].set()
            if case == 'stale_http':
                assert state['release'].wait(10)
            self.answer(403 if case == 'failed_http' or (case == 'retry_http' and len(state['posts']) == 1) else 202, {})
    peer = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server = threading.Thread(target=peer.serve_forever, daemon=True)
    server.start()
    def finish_peer():
        peer.shutdown()
        server.join(10)
        peer.server_close()
        (root / 'http-access-log.json').write_text(json.dumps(state['access_log']) + '\n')
        assert not server.is_alive() and state['responses']
        assert Counter(state['access_log']) == Counter(f'"{request}" {status} -' for request, status in state['responses'])
        assert len(state['access_log']) == len(state['gets']) + len(state['posts'])
        assert all(token not in record and 'Authorization' not in record for record in state['access_log'])
    client = StudentActionsClient('student/project', token=token, branch='main',
        repository_root=Path(__file__).resolve().parents[2], artifact_dir=root / 'http-artifacts',
        api_url=f'http://127.0.0.1:{peer.server_port}', allow_loopback=True)
    if case == 'probe_http':
        try:
            return _probe_review_case(gui, client, submission, state)
        finally:
            finish_peer()
    context = gui._new_remote_stop('actions')
    gui._actions_running = True
    gui._pipeline_running = True
    # A real current-result sentinel must not be replaced by cancellation.
    previous = gui._last_module_result = object()  # Opaque selected-result marker, no scientific data.
    original_geometry = gui.matrix_geometry.value
    try:
        if case != 'pending_http':
            gui._actions_client, gui._actions_submission = client, dict(submission)
            gui._bind_remote_stop('actions', client, submission, context)
        gui._refresh_running_jobs()
        gui.guided_cancel.click()
        assert gui._pipeline_cancellation.is_set()
        assert context['requested'] and gui._actions_running
        if case == 'pending_http':
            assert not state['gets'] and not state['posts']
            assert 'waiting for the calculation service to confirm this job' in gui.guided_jobs_status.value
            gui._actions_client, gui._actions_submission = client, dict(submission)
            gui._bind_remote_stop('actions', client, submission, context)
            pending = client.status(submission)
            assert pending.get('run_id') is None and not state['posts']
            state['registered'] = True
            observed = client.status(pending)
            gui._actions_submission = dict(observed)
            gui._bind_remote_stop('actions', client, observed, context)
        if case == 'stale_http':
            assert state['entered'].wait(10)
            old_worker = context['worker']
            newer = dict(submission, request_id=str(uuid.uuid4()), run_id=456)
            current = gui._new_remote_stop('actions')
            # The old worker must retain both its original client and request.
            gui._actions_client = StudentActionsClient('different/project', token=token,
                api_url=f'http://127.0.0.1:{peer.server_port}', allow_loopback=True)
            gui._actions_submission = newer
            gui._bind_remote_stop('actions', gui._actions_client, newer, current)
            before = gui.guided_jobs_status.value
            state['release'].set()
            old_worker.join(10)
            assert not old_worker.is_alive()
            assert gui._remote_stops['actions'] is current and not current['requested']
            assert gui._actions_submission == newer and gui.guided_jobs_status.value == before
            assert state['posts'] == ['/repos/student/project/actions/runs/123/cancel']
            return
        worker = context['worker']
        worker.join(10)
        assert not worker.is_alive()
        assert gui._actions_running  # Cancel request never pretends a terminal observation.
        if case == 'failed_http':
            assert not context['sent'] and 'could not be confirmed' in gui.guided_jobs_status.value
            assert not gui.guided_cancel.disabled
        elif case == 'retry_http':
            assert context['retry_required'] and not context['sent']
            observed = client.status(submission)
            gui._bind_remote_stop('actions', client, observed, context)
            assert len(state['posts']) == 1  # Polling cannot turn an error into a cancel storm.
            gui.guided_cancel.click()
            retried = context['worker']
            assert retried is not worker
            retried.join(10)
            assert not retried.is_alive() and context['sent']
            assert len(state['posts']) == 2
        elif case == 'wrong_http':
            assert not context['sent'] and not state['posts']
            assert 'identity does not match' in gui.guided_jobs_status.value
        elif case == 'terminal_http':
            assert context['sent'] and not state['posts']
            assert 'finished' in gui.guided_jobs_status.value
        else:
            assert context['sent'] and state['posts'] == ['/repos/student/project/actions/runs/123/cancel']
            gui.guided_cancel.click()
            assert context['worker'] is worker
            assert state['posts'] == ['/repos/student/project/actions/runs/123/cancel']
        assert gui._last_module_result is previous
        assert gui.matrix_geometry.value == original_geometry
    finally:
        state['release'].set()
        worker = context.get('worker')
        if worker is not None:
            worker.join(10)
        gui._actions_running = gui._pipeline_running = False
        finish_peer()


def _probe_review_case(gui, client, submission, state):
    """Actual HTTP failure through the production poll/final-state transitions."""
    from cochem_base.interfaces.student_actions import StudentActionsError
    context = gui._new_remote_stop('remote_probe')
    gui._remote_probe_client, gui._remote_probe_submission = client, dict(submission)
    gui._remote_probe_running = True
    gui._bind_remote_stop('remote_probe', client, submission, context)
    target = ('student/project', 'main')
    try:
        try:
            gui._poll_remote_engine_check(client, submission, context)
        except StudentActionsError:
            pass
        else:
            raise AssertionError('The real503 monitoring failure was not observed')
        gui._finish_remote_engine_check(context, target)
        assert gui._remote_probe_running and not gui.btn_remote_engine_cancel.disabled
        assert gui.btn_remote_engine_check.disabled and not gui.guided_cancel.disabled
        assert context['submission']['request_id'] == submission['request_id']
        gui.guided_cancel.click()
        context['worker'].join(10)
        assert not context['inflight'] and context['retry_required']
        assert gui._remote_probe_running and not state['posts']
        state['status_error'] = False
        gui.btn_remote_engine_cancel.click()
        context['worker'].join(10)
        assert not context['worker'].is_alive() and context['sent']
        assert state['posts'] == ['/repos/student/project/actions/runs/123/cancel']
        assert gui._remote_probe_running  # Request acceptance is not terminal.
        state['terminal'] = True
        current = gui._poll_remote_engine_check(client, context['submission'], context)
        assert current['status'] == 'completed'
        gui._finish_remote_engine_check(context, target)
        assert not gui._remote_probe_running and gui.guided_cancel.disabled
        assert not gui.btn_remote_engine_check.disabled and gui.btn_remote_engine_cancel.disabled
        # The peer supplies workflow states only, never a readiness/science report.
        assert not any(item.get('provisionable') for item in gui._remote_engine_availability.values())
    finally:
        worker = context.get('worker')
        if worker:
            worker.join(10)
        gui._remote_probe_running = False


def _hpc_review_case(gui, root, case):
    import hashlib
    import json
    import uuid

    if hasattr(gui, '_hpc_history_worker'):
        gui._hpc_history_worker.join(10)
    identity = str(uuid.uuid4())
    if case in {'hpc_unknown', 'hpc_unknown_corrupt', 'hpc_unknown_history', 'hpc_stale_history'}:
        from cochem_base.interfaces.student_hpc import SCHEMA, StudentHpcClient
        client = StudentHpcClient(artifact_dir=Path(os.environ['COCHEM_ARTIFACT_DIR']))
        package = client.jobs / identity
        package.mkdir(parents=True)
        (package / 'request.json').write_text(json.dumps({'schema_version': SCHEMA, 'request_id': identity, 'scheduler': 'slurm'}))
        (package / 'submit.sh').write_text('# Engineering protocol fixture; never executed.\n')
        attempt = client._record_dispatch_attempt(package, 'slurm')
        known = None
        if case in {'hpc_unknown_history', 'hpc_stale_history'}:
            older = client.jobs / str(uuid.uuid4())
            older.mkdir()
            (older / 'request.json').write_text(json.dumps({'schema_version': SCHEMA, 'request_id': older.name, 'scheduler': 'slurm'}))
            (older / 'submit.sh').write_text('# Earlier protocol record; never executed.\n')
            known_attempt = client._record_dispatch_attempt(older, 'slurm')
            known = client._accept_dispatch_ack(known_attempt, '456')
        if case == 'hpc_unknown_corrupt':
            path = package / 'dispatch-attempt.json'
            path.chmod(0o600)
            path.write_text('{')
        gui._hpc_client = client
        gui._refresh_student_hpc_history()
        assert gui._hpc_unknown_active and gui._hpc_running and gui._hpc_submission is None
        assert gui.btn_slurm_submit.disabled and not gui.guided_cancel.disabled
        assert not gui.btn_cancel.disabled
        gui.btn_cancel.click()  # The enabled main control must latch unknown Stop too.
        main_context = gui._remote_stops['hpc']
        assert main_context['requested'] and 'worker' not in main_context
        gui.guided_cancel.click()
        context = gui._remote_stops['hpc']
        assert context is main_context
        assert context['requested'] and 'worker' not in context
        assert 'waiting for the calculation service to confirm this job' in gui.guided_jobs_status.value
        before = sorted(client.jobs.iterdir())
        if case == 'hpc_stale_history':
            import threading
            entered, release = threading.Event(), threading.Event()
            gated = {'done': False}
            known_path = Path(known['package']) / 'submission.json'
            def delay_real_history_read(event, arguments):
                if event != 'open' or gated['done'] or threading.current_thread() is not history_worker:
                    return
                try:
                    target = Path(os.fsdecode(arguments[0]))
                except (TypeError, ValueError):
                    return
                if target == known_path:
                    gated['done'] = True
                    entered.set()
                    assert release.wait(10)
            # Actual file read pauses an old callback generation. No widget,
            # API, parser or scheduler function is replaced.
            history_worker = threading.Thread(target=gui._refresh_student_hpc_history)
            sys.addaudithook(delay_real_history_read)
            try:
                history_worker.start()
                assert entered.wait(10)
                gui._hpc_job_serial += 1  # Explicit newer protocol-generation state, no job submitted.
                context = gui._new_remote_stop('hpc')
                gui.guided_cancel.click()
                message = gui.slurm_status_output.value
                release.set()
                history_worker.join(10)
                assert not history_worker.is_alive()
                assert gui._remote_stops['hpc'] is context and context['requested']
                assert gui.slurm_status_output.value == message
                assert gui._hpc_unknown_attempt == attempt and gui._hpc_submission is None
            finally:
                release.set()
                history_worker.join(10)
        if known is not None:
            gui._refresh_student_hpc_history()
            assert gui._hpc_submission is None
            assert gui._remote_stops['hpc'] is context and context['requested']
            assert 'worker' not in context  # No B status/cancel controller request.
        gui._submit_student_hpc()
        assert sorted(client.jobs.iterdir()) == before and gui._hpc_submission is None
        second = type(gui)()
        second._hpc_history_worker.join(10)
        assert second._hpc_unknown_active and second._hpc_running and second._hpc_submission is None
        assert not second.guided_cancel.disabled and second.btn_slurm_submit.disabled
        assert 'Contact the instructor or cluster support' in second.slurm_status_output.value
        if case in {'hpc_unknown', 'hpc_unknown_history', 'hpc_stale_history'}:
            assert second._hpc_unknown_attempt == attempt and 'job_id' not in attempt
        else:
            assert second._hpc_unknown_attempt is None
        return
    if case == 'hpc_timeout':
        class EngineeringTimeoutBoundary:
            """GUI exception-state boundary only: never a scheduler/client substitute."""
            def __init__(self):
                self.calls = []
            def cancel(self, submission):
                self.calls.append(dict(submission))
                # Actual child timeout, the same documented exception class
                # propagated by StudentHpcClient._command(timeout=30).
                subprocess.run([sys.executable, '-B', '-c', 'import time;time.sleep(1)'],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=.05, check=True)
        client = EngineeringTimeoutBoundary()
        saved = {'request_id': identity, 'job_id': 'engineering-timeout-boundary'}
        gui._hpc_running = True
        gui._hpc_client, gui._hpc_submission = client, saved
        context = gui._new_remote_stop('hpc')
        gui._bind_remote_stop('hpc', client, saved, context)
        gui._refresh_running_jobs()
        gui.guided_cancel.click()
        context['worker'].join(10)
        assert not context['worker'].is_alive()
        assert context['requested'] and not context['inflight'] and context['retry_required']
        assert not context['sent'] and gui._hpc_running and not gui.guided_cancel.disabled
        assert 'could not be confirmed' in gui.guided_jobs_status.value
        gui.guided_cancel.click()
        context['worker'].join(10)
        assert len(client.calls) == 2 and all(item == saved for item in client.calls)
        assert not context['inflight'] and context['retry_required']
        assert gui._hpc_submission == saved
        gui._hpc_running = False
        return
    from cochem_base.interfaces.student_hpc import SCHEMA, StudentHpcClient
    import cochem_base.interfaces.student_hpc as student_hpc
    assert Path(student_hpc.__file__).resolve() == Path(__file__).resolve().parents[2] / 'src/cochem_base/interfaces/student_hpc.py'
    client = StudentHpcClient(artifact_dir=root / 'hpc-artifacts')
    package = client.jobs / identity
    package.mkdir(parents=True)
    original = b'{"schema_version":"retained-engineering-request"}'
    (package / 'request.json').write_bytes(original)
    saved = {'schema_version': SCHEMA, 'request_id': identity, 'scheduler': 'slurm', 'job_id': '123',
        'package': str(package), 'request_sha256': hashlib.sha256(original).hexdigest(),
        'submitted_at': 'retained protocol-state control'}
    (package / 'submission.json').write_text(json.dumps(saved))
    # Actual protected API must refuse before even looking for a scheduler,
    # on every platform. No scancel/qdel fake or real command is installed/run.
    (package / 'request.json').write_bytes(original + b' ')
    other = dict(saved, request_id=str(uuid.uuid4()), job_id='456', status='completed')
    gui._hpc_client, gui._hpc_submission = client, dict(saved)
    gui._hpc_running = True
    gui._hpc_history = {identity: saved, other['request_id']: other}
    gui.hpc_history.options = [('ActiveA', identity), ('CompletedB', other['request_id'])]
    gui.hpc_history.value = other['request_id']
    gui._hpc_job_serial += 1
    serial = gui._hpc_job_serial
    context = gui._new_remote_stop('hpc')
    gui._bind_remote_stop('hpc', client, saved, context)
    observed_reads = []
    target = package / 'submission.json'
    def observe_owned_read(event, arguments):
        if event == 'open':
            try:
                if Path(os.fsdecode(arguments[0])) == target:
                    observed_reads.append(str(target))
            except (TypeError, ValueError):
                pass
    sys.addaudithook(observe_owned_read)
    gui._open_student_hpc_history()
    assert gui._hpc_submission == saved and gui._hpc_job_serial == serial and gui._hpc_running
    assert gui._remote_stops['hpc'] is context
    assert 'owned request remains selected' in gui.slurm_status_output.value
    gui._refresh_execution_gate()
    assert gui.btn_hpc_open.disabled and not gui.guided_cancel.disabled
    gui.guided_cancel.click()
    context['worker'].join(10)
    assert not context['worker'].is_alive() and observed_reads
    assert gui._hpc_submission == saved and context['submission']['request_id'] == identity
    assert context['retry_required'] and not context['inflight']
    assert 'Original HPC request changed' in gui.guided_jobs_status.value
    assert gui._hpc_running  # Protected refusal does not lose the tracked identity.
    gui._hpc_running = False


if __name__ == '__main__':
    _exercise(sys.argv[1], Path(sys.argv[2]))
