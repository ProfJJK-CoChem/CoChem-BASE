"""Actual Git/loopback cache counts, never hosted throughput or scientific proof."""
from __future__ import annotations

import base64
from collections import Counter
from copy import deepcopy
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import runpy
import subprocess
import threading
import time
import urllib.parse
import uuid

import pytest

from cochem_base.interfaces import student_actions_admission as admission
from cochem_base.interfaces import student_actions_admission_git as hosted
from cochem_base.interfaces.student_actions import StudentActionsClient

ROOT = Path(__file__).resolve().parents[2]
_fixtures = runpy.run_path(str(Path(__file__).with_name('test_student_actions_admission.py')),
                         run_name='immutable_cache_engineering_fixture')


class CacheHandler(_fixtures['GitHandler']):
    def reply(self, value, status=200):
        if getattr(self.server, 'corrupt_blob_reply', False) and '/git/blobs/' in self.path:
            value = {**value, 'size': value['size']+1}
        return super().reply(value, status)

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        if '/contents/' in parsed.path:
            self.server.gets.append(self.path)
            repository, relative = parsed.path.removeprefix('/repos/').split('/contents/', 1)
            revision = urllib.parse.parse_qs(parsed.query).get('ref', [''])[0]
            if (repository not in {self.server.repository, 'ProfJJK-CoChem/CoChem-BASE'}
                    or relative not in admission.REQUIRED_PATHS | {admission.DESCRIPTOR_PATH}
                    or revision != self.server.qualified_fixture_revision):
                self.reply({'error': 'unqualified engineering source identity'}, 404)
                return
            unused_code, raw = self.server.store.git('show', revision + ':' + relative)
            self.reply({'type': 'file', 'path': relative, 'sha': admission.blob_id(raw),
                'size': len(raw), 'encoding': 'base64', 'content': base64.b64encode(raw).decode()})
            return
        return super().do_GET()


class CacheServer(ThreadingHTTPServer):
    """Owned real loopback server retaining the stopped fixture's exact state."""

    def __init__(self, previous):
        super().__init__(('127.0.0.1', 0), CacheHandler)
        self.posts = previous.posts
        self.runs = previous.runs
        self.gets = previous.gets
        self.access = previous.access
        self.protected = previous.protected
        self.cancels = previous.cancels
        self.ref_updates = previous.ref_updates
        self.lock = previous.lock
        self.store = previous.store
        self.repository = previous.repository
        self.repository_id = previous.repository_id
        self.workflow_id = previous.workflow_id
        self.drop_ref_ack = previous.drop_ref_ack
        self.drop_dispatch_ack = previous.drop_dispatch_ack
        self.observation_override = previous.observation_override
        self.git_writes = previous.git_writes
        self.drop_create_ack = previous.drop_create_ack
        self.drop_patch_ack = previous.drop_patch_ack
        self.listing_extra = previous.listing_extra
        self.listing_change_page = previous.listing_change_page
        self.daemon_threads = True


@pytest.fixture
def cache_peer(tmp_path, request):
    controller = _fixtures['Controls']('test_exact_transport_original_bytes_and_noncircular_anchor')
    controller._testMethodName = request.node.name
    controller.setUp()
    # Replace only the actual HTTP server before it serves any workload; no
    # production transport or callable is patched or substituted.
    controller.peer.shutdown()
    controller.peer.server_close()
    controller.thread.join(timeout=3)
    assert not controller.thread.is_alive()
    peer = CacheServer(controller.peer)
    controller.peer = peer
    controller.thread = threading.Thread(target=peer.serve_forever, daemon=True)
    controller.thread.start()
    controller.url = f'http://127.0.0.1:{peer.server_port}'
    controller.api = StudentActionsClient(peer.repository, branch='main', token='engineering-only-token',
        repository_root=tmp_path / 'source', artifact_dir=tmp_path / 'runtime',
        api_url=controller.url, allow_loopback=True)
    controller.observations = []
    try:
        yield controller
    finally:
        evidence = os.environ.get('ADMISSION_ENGINEERING_EVIDENCE')
        if evidence:
            out = Path(evidence)
            out.mkdir(parents=True, exist_ok=True)
            (out / (request.node.name + '-cache-counts.json')).write_text(json.dumps({
                'scope': 'Actual local Git and loopback HTTP counts, not GitHub rate-limit or science acceptance',
                'observations': controller.observations,
                'source_sha256': hashlib.sha256(Path(hosted.__file__).read_bytes()).hexdigest(),
            }, sort_keys=True, indent=2) + '\n')
        controller.tearDown()


def _qualified_source(peer, tmp_path):
    """Commit actual protected bytes to a real owned Git source fixture."""
    source = tmp_path / 'protected-source'
    source.mkdir()
    members = sorted(admission.REQUIRED_PATHS | {admission.DESCRIPTOR_PATH})
    for relative in members:
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull, GIT_CONFIG_NOSYSTEM='1',
        GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0', GIT_AUTHOR_NAME='Engineering source fixture',
        GIT_AUTHOR_EMAIL='fixture@example.invalid', GIT_COMMITTER_NAME='Engineering source fixture',
        GIT_COMMITTER_EMAIL='fixture@example.invalid')
    def git(*args):
        return subprocess.run(['git', '-C', str(source), '-c', 'core.hooksPath='+os.devnull, *args],
            env=environment, check=True, capture_output=True, timeout=15).stdout
    git('init')
    git('add', '--', *members)
    git('commit', '-m', 'Actual protected bytes for loopback source-envelope engineering only')
    revision = git('rev-parse', 'HEAD').decode().strip()
    peer.store.git('fetch', '--no-tags', str(source), revision)
    peer.qualified_fixture_revision = revision
    return revision


def _history(controller, jobs, revision=None):
    """Four real Git transitions/job; terminal failure records imply no science.

    Direct fixture construction avoids O(N²) REST traffic just to arrange an
    immutable historical graph. Production AdmissionStore validates the entire
    actual graph through HTTP in each measured read below.
    """
    backend = controller.store.backend
    parent = None
    for index in range(jobs):
        request = deepcopy(controller.request)
        request['request_id'] = str(uuid.uuid5(uuid.NAMESPACE_URL, f'engineering-request-{index}'))
        if revision is not None:
            request.update(source_sha=revision, worker_source_sha=revision)
        raw = admission.canonical(request)
        generation = str(uuid.uuid5(uuid.NAMESPACE_URL, f'engineering-generation-{index}'))
        intent = {'schema_version': 'cochem.student-actions-intent/1', 'protocol': admission.PROTOCOL,
            'generation': generation, 'repository_id': 17, 'repository': request['repository'],
            'branch': 'main', 'workflow_id': 37, 'workflow_path': '.github/workflows/student_research.yml',
            'request_id': request['request_id'], 'payload_sha256': admission.digest(raw),
            'request_blob_sha': admission.blob_id(raw), 'source_sha': request['source_sha'],
            'worker_source_sha': request['worker_source_sha']}
        intent_raw = admission.canonical(intent)
        state = {'schema_version': 'cochem.student-actions-state/1', 'generation': generation,
            'intent_sha256': admission.digest(intent_raw), 'phase': 'prepared', 'previous': parent,
            'actor': None, 'anchor': None, 'binding_sha256': None, 'stop_requested': False, 'terminal': None}
        files = {'request.json': raw, 'intent.json': intent_raw, 'state.json': admission.canonical(state)}
        commit = backend.commit(files, parent)
        backend.advance(commit, parent)
        parent = commit
        state.update(phase='dispatch_intent', previous=parent,
            actor=str(uuid.uuid5(uuid.NAMESPACE_URL, f'engineering-actor-{index}')))
        files['state.json'] = admission.canonical(state)
        anchor = backend.commit(files, parent)
        backend.advance(anchor, parent)
        parent = anchor
        binding = {'schema_version': 'cochem.student-actions-binding/1', 'generation': generation,
            'intent_sha256': state['intent_sha256'], 'anchor': anchor,
            **{key: intent[key] for key in ('request_id', 'payload_sha256', 'repository_id', 'repository',
                'workflow_id', 'branch', 'source_sha', 'worker_source_sha')}, 'run_id': index+1001, 'run_attempt': 1}
        files['binding.json'] = admission.canonical(binding)
        state.update(phase='bound', previous=parent, anchor=anchor,
            binding_sha256=admission.digest(files['binding.json']))
        files['state.json'] = admission.canonical(state)
        commit = backend.commit(files, parent)
        backend.advance(commit, parent)
        parent = commit
        state.update(phase='terminal', previous=parent, terminal={'kind': 'confirmed_run_terminal',
            'run_id': binding['run_id'], 'run_attempt': 1, 'conclusion': 'failure'})
        files['state.json'] = admission.canonical(state)
        commit = backend.commit(files, parent)
        backend.advance(commit, parent)
        parent = commit
        controller.peer.runs.append({'id': binding['run_id'], 'run_attempt': 1,
            'repository': {'id': 17, 'full_name': request['repository']}, 'workflow_id': 37,
            'head_sha': request['source_sha'], 'head_branch': 'main', 'event': 'workflow_dispatch',
            'display_title': 'CoChem student '+request['request_id'], 'status': 'completed', 'conclusion': 'failure',
            'html_url': f"https://github.com/{request['repository']}/actions/runs/{binding['run_id']}"})
    return parent


def _counts(paths):
    counts = Counter()
    for path in paths:
        if '/git/ref/' in path:
            counts['ref'] += 1
        elif '/git/commits/' in path:
            counts['commits'] += 1
        elif '/git/trees/' in path:
            counts['trees'] += 1
        elif '/git/blobs/' in path:
            counts['blobs'] += 1
        elif '/contents/' in path:
            counts['capability'] += 1
        elif '/actions/runs/' in path:
            counts['runs'] += 1
    return dict(counts)


@pytest.mark.parametrize('jobs', [0, 5, 20, 50])
def test_three_cold_workflow_apis_warm_reads_and_client_refresh_actual_counts(cache_peer, tmp_path, jobs):
    controller = cache_peer
    revision = _qualified_source(controller.peer, tmp_path)
    tip = _history(controller, jobs, revision)
    cold_totals = []
    for barrier in range(3):
        api = hosted.ReadOnlyAPI('engineering-only-token', deadline=time.time()+120,
            api_url=controller.url, allow_loopback=True)
        start = len(controller.peer.gets)
        store = admission.AdmissionStore(hosted.GitAdmissionBackend(api, controller.peer.repository, read_only=True))
        snapshot = store.read()
        cold = _counts(controller.peer.gets[start:])
        assert cold == ({'ref': 1} if not jobs else {'ref': 1, 'commits': 4*jobs, 'trees': 4*jobs, 'blobs': 7*jobs})
        assert snapshot is None if not jobs else snapshot.tip == tip
        cold_totals.append(sum(cold.values()))
        start = len(controller.peer.gets)
        # Recreated backend, same actual API session; only immutable objects reuse.
        warmed = admission.AdmissionStore(hosted.GitAdmissionBackend(api, controller.peer.repository, read_only=True)).read()
        warm = _counts(controller.peer.gets[start:])
        assert warm == {'ref': 1}
        assert warmed is None if not jobs else warmed.tip == tip
        start = len(controller.peer.gets)
        hosted.qualify_capability(api, canonical_repository='ProfJJK-CoChem/CoChem-BASE', worker_sha=revision,
            repository=controller.peer.repository, source_sha=revision)
        capability = _counts(controller.peer.gets[start:])
        assert capability == {'capability': 2+2*len(admission.REQUIRED_PATHS)}
        controller.observations.append({'jobs': jobs, 'commits': 4*jobs, 'barrier': barrier,
            'cold': cold, 'warm_recreated_backend': warm, 'separate_capability': capability,
            'cache': api._admission_immutable_objects.statistics()})
    start = len(controller.peer.gets)
    client_store = admission.AdmissionStore(hosted.GitAdmissionBackend(controller.api, controller.peer.repository))
    snapshot = client_store.read()
    client_cold = _counts(controller.peer.gets[start:])
    if jobs:
        saved = controller.api._saved_admission(snapshot)
        start = len(controller.peer.gets)
        status = controller.api.status(saved)
        client_warm = _counts(controller.peer.gets[start:])
        assert client_warm == {'ref': 1, 'runs': 1}
        assert status['admission_terminal'] is True and status['run_id'] == snapshot.binding['run_id']
    else:
        start = len(controller.peer.gets)
        assert client_store.read() is None
        client_warm = _counts(controller.peer.gets[start:])
        assert client_warm == {'ref': 1}
    controller.observations.append({'jobs': jobs, 'three_cold_ledger_gets': sum(cold_totals),
        'client_cold_ledger': client_cold, 'normal_client_warm_status': client_warm,
        'hosted_rate_or_scientific_acceptance_claimed': False})


def test_cached_member_mapping_is_copied_and_new_transition_still_fetches(cache_peer):
    c = cache_peer
    tip = _history(c, 5)
    backend = hosted.GitAdmissionBackend(c.api, c.peer.repository)
    store = admission.AdmissionStore(backend)
    old = store.read()
    original, parent = backend.files(tip)
    state = original['state.json']
    original['state.json'] = b'foreign caller mutation'
    assert backend.files(tip)[0]['state.json'] == state
    request = deepcopy(c.request)
    request['request_id'] = str(uuid.uuid4())
    start = len(c.peer.gets)
    new = store.prepare(admission.canonical(request), repository_id=17, branch='main', workflow_id=37)
    count = _counts(c.peer.gets[start:])
    assert count['commits'] == 1 and count['trees'] == 1 and count['blobs'] == 3
    assert new.tip != old.tip and new.state['phase'] == 'prepared'
    start = len(c.peer.gets)
    recreated = admission.AdmissionStore(hosted.GitAdmissionBackend(c.api, c.peer.repository))
    assert recreated.read().tip == new.tip
    assert _counts(c.peer.gets[start:]) == {'ref': 1}
    writes = len(c.peer.git_writes)
    with pytest.raises(admission.AdmissionError, match='captured project request changed'):
        recreated.stop(admission.identity(old))
    assert len(c.peer.git_writes) == writes and recreated.read().state['stop_requested'] is False
    c.observations.append({'new_transition': count, 'recreated_backend_state_guard': 'refused old request'})


def test_same_backend_rewind_and_recreated_backend_generation_are_separate(cache_peer):
    c = cache_peer
    store = admission.AdmissionStore(hosted.GitAdmissionBackend(c.api, c.peer.repository))
    prepared = store.prepare(admission.canonical(c.request), repository_id=17, branch='main', workflow_id=37)
    withdrawn = store.stop(admission.identity(prepared))
    assert store.read().state['stop_requested'] is True
    request = dict(c.request, request_id=str(uuid.uuid4()))
    newer = store.prepare(admission.canonical(request), repository_id=17, branch='main', workflow_id=37)
    recreated = admission.AdmissionStore(hosted.GitAdmissionBackend(c.api, c.peer.repository))
    with pytest.raises(admission.AdmissionError, match='captured project request changed'):
        recreated.resume(admission.identity(prepared))
    c.store.git('update-ref', c.store.ref, withdrawn.tip)
    start = len(c.peer.gets)
    with pytest.raises(admission.AdmissionError, match='replaced or rewound'):
        store.read()
    assert _counts(c.peer.gets[start:])['ref'] == 1
    # A new backend has no session-wide mutable seen-tip authority. Its full
    # history/parser and captured generation guard, not the cache, refuse B→A.
    another = admission.AdmissionStore(hosted.GitAdmissionBackend(c.api, c.peer.repository))
    with pytest.raises(admission.AdmissionError, match='captured project request changed'):
        another.stop(admission.identity(newer))
    assert not c.peer.posts and not c.peer.cancels


def test_cache_isolation_between_clients_and_repository_names(cache_peer, tmp_path):
    c = cache_peer
    tip = _history(c, 5)
    admission.AdmissionStore(hosted.GitAdmissionBackend(c.api, c.peer.repository)).read()
    second = StudentActionsClient(c.peer.repository, branch='main', token='engineering-only-token',
        api_url=c.url, allow_loopback=True, repository_root=tmp_path/'other-source', artifact_dir=tmp_path/'other-runtime')
    start = len(c.peer.gets)
    admission.AdmissionStore(hosted.GitAdmissionBackend(second, c.peer.repository)).read()
    assert _counts(c.peer.gets[start:]) == {'ref': 1, 'commits': 20, 'trees': 20, 'blobs': 35}
    assert c.api._admission_immutable_objects is not second._admission_immutable_objects
    start = len(c.peer.gets)
    other_repository = hosted.GitAdmissionBackend(c.api, 'engineering/not-authorized')
    with pytest.raises(admission.TransportError):
        other_repository.files(tip)
    assert any('/repos/engineering/not-authorized/git/commits/' in path for path in c.peer.gets[start:])


def test_logically_malformed_state_is_cached_only_as_bytes_and_repeatedly_refused(cache_peer):
    c = cache_peer
    store = admission.AdmissionStore(hosted.GitAdmissionBackend(c.api, c.peer.repository))
    prepared = store.prepare(admission.canonical(c.request), repository_id=17, branch='main', workflow_id=37)
    files, unused_parent = c.store.files(prepared.tip)
    state = admission.strict(files['state.json'])
    state['unsupported'] = 'No state authorization is cached'
    files['state.json'] = admission.canonical(state)
    corrupt = c.store.commit(files, prepared.tip)
    c.store.advance(corrupt, prepared.tip)
    for attempt in range(2):
        start = len(c.peer.gets)
        with pytest.raises(admission.AdmissionError, match='Invalid state'):
            store.read()
        if attempt == 1:
            assert _counts(c.peer.gets[start:]) == {'ref': 1}
    assert not c.peer.posts and not c.peer.cancels


def test_oversized_immutable_git_blob_is_never_cached(cache_peer):
    c = cache_peer
    files = {'request.json': b'x'*(admission.MAX_TRANSPORT+1), 'intent.json': b'{}', 'state.json': b'{}'}
    commit = c.store.commit(files, None)
    backend = hosted.GitAdmissionBackend(c.api, c.peer.repository)
    for unused in range(2):
        start = len(c.peer.gets)
        with pytest.raises(admission.AdmissionError, match='blob identity'):
            backend.files(commit)
        assert _counts(c.peer.gets[start:])['commits'] == 1
        assert c.api._admission_immutable_objects.statistics()['commits'] == 0
        assert c.api._admission_immutable_objects.statistics()['payload_bytes'] == 0


def test_fifo_commit_eviction_is_bounded_and_actual_http_refetches(cache_peer):
    c = cache_peer
    backend = hosted.GitAdmissionBackend(c.api, c.peer.repository)
    commits = []
    for index in range(hosted.MAX_CACHE_COMMITS+1):
        # Object-verifier-only records, not admitted requests or scientific outputs.
        files = {'request.json': admission.canonical({'engineering_object_only': index}),
                 'intent.json': b'{}', 'state.json': b'{}'}
        commit = c.store.commit(files, None)
        commits.append(commit)
        actual, parent = backend.files(commit)
        assert actual == files and parent is None
        stats = c.api._admission_immutable_objects.statistics()
        assert stats['commits'] <= 256 and stats['payload_bytes'] <= 64*1024*1024
    assert c.api._admission_immutable_objects.statistics()['commits'] == 256
    start = len(c.peer.gets)
    backend.files(commits[-1])
    assert len(c.peer.gets) == start  # A hit does not change FIFO insertion order.
    start = len(c.peer.gets)
    backend.files(commits[0])
    assert _counts(c.peer.gets[start:]) == {'commits': 1, 'trees': 1, 'blobs': 1}
    c.observations.append({'eviction_refetch': _counts(c.peer.gets[start:]),
        'cache': c.api._admission_immutable_objects.statistics(), 'maximum_history_unchanged': admission.MAX_HISTORY})


def test_malformed_git_blob_metadata_is_not_cached_and_can_be_refetched(cache_peer):
    c = cache_peer
    tip = _history(c, 1)
    backend = hosted.GitAdmissionBackend(c.api, c.peer.repository)
    c.peer.corrupt_blob_reply = True
    with pytest.raises(admission.AdmissionError, match='blob identity'):
        backend.files(tip)
    assert c.api._admission_immutable_objects.statistics()['commits'] == 0
    assert c.api._admission_immutable_objects.statistics()['payload_bytes'] == 0
    c.peer.corrupt_blob_reply = False
    start = len(c.peer.gets)
    files, parent = backend.files(tip)
    assert _counts(c.peer.gets[start:]) == {'commits': 1, 'trees': 1, 'blobs': 4}
    assert files['state.json'] and parent is not None
    start = len(c.peer.gets)
    assert backend.files(tip) == (files, parent)
    assert len(c.peer.gets) == start
