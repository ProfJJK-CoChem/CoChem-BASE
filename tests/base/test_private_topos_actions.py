"""Strict request and transport algebra, without remote/provider substitutes.

Metadata examples exercise pure identity comparisons only. No supplied dictionary
is claimed to be a real GitHub release, calculation, or scientific observation.
The provider probe below executes the real TOPOS model/classifier without engines.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from cochem_base.interfaces.private_actions import _canonical
from cochem_base.interfaces.private_topos_actions import (
    _PROBE,
    SCHEMA,
    WORKFLOW,
    kit_marker,
    load_bundle,
)
from scripts.consume_private_engine_asset import validate_calculation_intent
from scripts.private_engine_assets import _calculation
from scripts.private_topos_job import load_hosted_budget, validate_bound_request, validate_intent


@pytest.fixture
def typed_request():
    from topos.models import Molecule, RunRequest
    return RunRequest(molecule=Molecule(symbols=['O', 'H', 'H'],
        coordinates=[[0.0, 0.0, 0.0], [0.9572, 0.0, 0.0], [-0.239, 0.927, 0.0]],
        charge=0, multiplicity=1), purpose='energy', engine='xtb', method='GFN2-xTB',
        threads=1, memory_mb=512, budget_seconds=30.0).model_dump(mode='json')


@pytest.fixture
def intent(typed_request):
    return {'kind': 'topos/1', 'job_file': 'jobs/input.json',
        'input_sha256': hashlib.sha256(_canonical(typed_request)).hexdigest(), 'cores': 1,
        'maxcore_mb': 512, 'memory_mb': 512, 'budget_seconds': 30.0, 'receiver_timeout': 90,
        'source_pins': {'base': 'a' * 40, 'topos': 'b' * 40, 'torq': 'c' * 40}, 'kit_sha256': 'd' * 64}


@pytest.fixture
def bundle(intent):
    now = datetime.now(timezone.utc) - timedelta(seconds=2)
    task = 'e' * 32
    return {'schema_version': SCHEMA, 'task_id': task, 'repository': 'algebra/project',
        'repository_id': 17, 'owner_id': 19, 'ref': 'refs/heads/main', 'source_sha': 'f' * 40,
        'intent': intent, 'kit': {'release_tag': 'cochem-topos-kit-' + task, 'release_id': 23,
            'asset_id': 29, 'asset_name': 'mandatory-kit.zip', 'sha256': intent['kit_sha256'], 'size_bytes': 123},
        'engines': {}, 'required_engines': ['xtb'], 'created_at': now.isoformat(),
        'expires_at': (now + timedelta(hours=1)).isoformat()}


def test_explicit_free_transport_plan_loads_without_claiming_provider_acceptance(bundle):
    raw = _canonical(bundle)
    assert load_bundle(raw, hashlib.sha256(raw).hexdigest()) == bundle
    assert 'scientific' not in bundle


def declared_engine_plan(bundle, engines):
    # Reuse the existing explicitly mathematical schema-domain helper. Its
    # descriptor metadata is real; none of its IDs assert a provider response.
    from tests.test_private_engine_assets_integrity import _mathematical_receipt, _seal_intent
    bundle['required_engines'] = sorted([*engines, 'xtb'])
    for engine in engines:
        receipt = _mathematical_receipt(engine)
        receipt['destination'].update(repository=bundle['repository'], repository_id=bundle['repository_id'],
                                      owner_id=bundle['owner_id'])
        receipt['project'].update(ref=bundle['ref'], source_sha=bundle['source_sha'], workflow_path=WORKFLOW,
                                  calculation=bundle['intent'])
        _seal_intent(receipt)
        bundle['engines'][engine] = {'receipt': receipt, 'sha256': hashlib.sha256(_canonical(receipt)).hexdigest(),
                                    'task_id': receipt['task_id']}
    return bundle


@pytest.mark.parametrize('engines', [('orca',), ('cfour',), ('orca', 'cfour')])
def test_one_and_two_engine_schema_plans_preserve_separate_original_receipts(bundle, engines):
    from tests.test_private_engine_assets_integrity import _seal_intent
    declared_engine_plan(bundle, engines)
    raw = _canonical(bundle)
    parsed = load_bundle(raw, hashlib.sha256(raw).hexdigest())
    assert parsed['engines'] == bundle['engines']
    assert len({entry['task_id'] for entry in parsed['engines'].values()}) == len(engines)
    changed = copy.deepcopy(bundle)
    first = engines[0]
    changed['engines'][first]['receipt']['project']['source_sha'] = '8' * 40
    _seal_intent(changed['engines'][first]['receipt'])
    changed['engines'][first]['sha256'] = hashlib.sha256(_canonical(changed['engines'][first]['receipt'])).hexdigest()
    raw = _canonical(changed)
    with pytest.raises(ValueError, match='same exact'):
        load_bundle(raw, hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize('key,value', [
    ('task_id', 7), ('source_sha', None), ('required_engines', [True]),
    ('created_at', {}), ('repository_id', True), ('schema_version', 'other'),
    ('engines', {'orca': {}}), ('required_engines', ['orca', 'xtb']),
    ('required_engines', ['xtb', 'xtb']), ('owner_id', 0),
])
def test_malformed_or_incomplete_bundle_rejects_before_any_remote_operation(bundle, key, value):
    bundle[key] = value
    raw = _canonical(bundle)
    with pytest.raises(ValueError):
        load_bundle(raw, hashlib.sha256(raw).hexdigest())


def test_bundle_rejects_changed_bytes_and_noncanonical_representation(bundle):
    raw = _canonical(bundle)
    digest = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match='byte identity'):
        load_bundle(raw + b' ', digest)
    with pytest.raises(ValueError, match='canonical'):
        changed = json.dumps(bundle, indent=2).encode()
        load_bundle(changed, hashlib.sha256(changed).hexdigest())


def test_kit_ownership_marker_binds_engine_plan_and_exact_request(bundle):
    original = kit_marker(bundle)
    changed = copy.deepcopy(bundle)
    changed['required_engines'] = ['crest', 'xtb']
    assert kit_marker(changed) != original
    changed = copy.deepcopy(bundle)
    changed['intent']['input_sha256'] = '9' * 64
    assert kit_marker(changed) != original


def test_expired_plan_only_remains_inspectable_for_terminal_lifecycle(bundle):
    now = datetime.now(timezone.utc)
    bundle.update(created_at=(now - timedelta(hours=2)).isoformat(), expires_at=(now - timedelta(hours=1)).isoformat())
    raw = _canonical(bundle)
    with pytest.raises(ValueError, match='lifetime'):
        load_bundle(raw, hashlib.sha256(raw).hexdigest())
    assert load_bundle(raw, hashlib.sha256(raw).hexdigest(), allow_expired=True) == bundle


@pytest.mark.parametrize('key,value', [
    ('cores', True), ('cores', 3), ('memory_mb', 4097), ('maxcore_mb', 511),
    ('receiver_timeout', 29), ('budget_seconds', float('nan')), ('job_file', '../input.json'),
    ('source_pins', {'base': 'a' * 40}), ('kit_sha256', '0' * 64),
])
def test_inexact_source_or_allocation_intent_is_rejected(intent, key, value):
    intent[key] = value
    with pytest.raises(ValueError):
        validate_intent(intent)


def test_legacy_molecular_intent_keeps_its_original_contract(intent):
    molecular = {key: intent[key] for key in ('job_file', 'input_sha256', 'cores', 'maxcore_mb')}
    assert _calculation('.github/workflows/orca_calculation.yml', molecular) == molecular
    assert _calculation(WORKFLOW, intent) == intent
    with pytest.raises(ValueError):
        _calculation('.github/workflows/orca_calculation.yml', intent)
    with pytest.raises(ValueError):
        _calculation(WORKFLOW, molecular)


def test_actual_committed_file_and_native_consumer_preserve_complete_typed_request(tmp_path, typed_request, intent):
    path = tmp_path / intent['job_file']
    path.parent.mkdir()
    path.write_bytes(_canonical(typed_request))
    environment = {'JOB_FILE': intent['job_file'], 'JOB_CORES': '1', 'JOB_MAXCORE_MB': '512'}
    assert validate_bound_request(tmp_path, intent, environment) == typed_request
    validate_calculation_intent({'project': {'workflow_path': WORKFLOW, 'calculation': intent}}, tmp_path, environment)
    altered = copy.deepcopy(typed_request)
    altered['molecule']['charge'] = 1
    path.write_bytes(_canonical(altered))
    with pytest.raises(ValueError, match='SHA-256'):
        validate_bound_request(tmp_path, intent, environment)


def test_real_provider_model_and_recipe_classifier_execute_without_native_engines(typed_request):
    result = subprocess.run([sys.executable, '-I', '-B', '-c', _PROBE], input=_canonical(typed_request),
        capture_output=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr.decode()
    selected = json.loads(result.stdout)
    assert selected['request'] == typed_request
    assert selected['native_engines'] == ['xtb']
    assert selected['cfour_parser_versions'] == {}


@pytest.mark.parametrize('mutation', ['missing-default', 'boolean-thread', 'duplicate-key'])
def test_real_provider_probe_rejects_incomplete_or_ambiguous_request(typed_request, mutation):
    if mutation == 'missing-default':
        typed_request.pop('device')
    elif mutation == 'boolean-thread':
        typed_request['threads'] = True
    raw = _canonical(typed_request)
    if mutation == 'duplicate-key':
        raw = raw[:-1] + b',"threads":2}'
    result = subprocess.run([sys.executable, '-I', '-B', '-c', _PROBE], input=raw,
        capture_output=True, timeout=60, check=False)
    assert result.returncode != 0
    assert not result.stdout


def test_worker_rejects_non_actions_context_before_provider_network(tmp_path, bundle):
    from scripts.run_private_topos_actions import worker_bundle
    raw = _canonical(bundle)
    names = ('TOPOS_STAGING_BUNDLE', 'TOPOS_STAGING_BUNDLE_SHA256', 'GITHUB_ACTIONS')
    previous = {key: os.environ.get(key) for key in names}
    try:
        os.environ.update(TOPOS_STAGING_BUNDLE=raw.decode(),
            TOPOS_STAGING_BUNDLE_SHA256=hashlib.sha256(raw).hexdigest(), GITHUB_ACTIONS='false')
        with pytest.raises(ValueError, match='owning project'):
            worker_bundle(tmp_path)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_hosted_budget_bound_file_survives_credential_free_boundary_and_rejects_changed_authority(tmp_path, typed_request):
    typed_request['include_queue_in_budget'] = True
    control = {'schema_version': 'cochem.topos-hosted-budget/1',
        'request_sha256': hashlib.sha256(_canonical(typed_request)).hexdigest(),
        'repository': 'algebra/project', 'repository_id': 17, 'owner_id': 19,
        'source_sha': 'a' * 40, 'ref': 'refs/heads/main', 'workflow_path': WORKFLOW,
        'run_id': 23, 'run_attempt': 1, 'workflow_created_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}
    environment = {'GITHUB_ACTIONS': 'true', 'GITHUB_WORKFLOW_REF': f"algebra/project/{WORKFLOW}@refs/heads/main"}
    for variable, key in (('GITHUB_REPOSITORY', 'repository'), ('GITHUB_REPOSITORY_ID', 'repository_id'),
        ('GITHUB_REPOSITORY_OWNER_ID', 'owner_id'), ('GITHUB_SHA', 'source_sha'), ('GITHUB_REF', 'ref'),
        ('GITHUB_RUN_ID', 'run_id'), ('GITHUB_RUN_ATTEMPT', 'run_attempt')):
        environment[variable] = str(control[key])
    source = tmp_path / 'source-bound-budget.json'
    source.write_bytes(_canonical(control))
    assert load_hosted_budget(source, typed_request, environment) == control
    assert not any('TOKEN' in name for name in environment)
    with pytest.raises(ValueError, match='differ'):
        load_hosted_budget(source, typed_request, {**environment, 'GITHUB_RUN_ATTEMPT': '2'})
    with pytest.raises(ValueError, match='differ'):
        load_hosted_budget(source, {**typed_request, 'budget_seconds': 31.0}, environment)


def test_actual_base_gui_selects_topos_and_blocks_missing_request_before_network(tmp_path):
    root = Path(__file__).resolve().parents[2]
    code = """from ui.voila_layout.cochem_gui import CoChemGUI
gui = CoChemGUI()
gui.calc_env_dropdown.value = 'github-actions'
gui.gh_repo_input.value = 'algebra/project'
gui.actions_pathway.value = 'topos'
assert gui.actions_topos_panel.layout.display == ''
assert gui.actions_memory.disabled and gui.actions_cores.disabled
assert set(gui.actions_topos_descriptors) == {'orca','cfour'}
gui._run_private_actions('submit')
assert 'Drop or select the complete TOPOS request' in gui.actions_lifecycle_status.value
assert not gui._actions_lifecycle_running
assert gui.actions_task_id.value == ''
assert len(gui.actions_topos_upload._trait_values) > 0
gui.module_recipient.value = 'torq'
assert not gui.btn_torq_dashboard.disabled
assert gui.btn_module_dashboard.disabled
assert gui.btn_torq_dashboard_stop.disabled
assert gui.torq_dashboard_port.value == 8888
assert gui._torq_dashboard is None
gui.app.close()
"""
    environment = {**os.environ, 'PYTHONPATH': str(root / 'src') + os.pathsep + str(root),
        'COCHEM_CONFIG': str(tmp_path / 'absent-registry.json'), 'COCHEM_ARTIFACT_DIR': str(tmp_path / 'runtime')}
    result = subprocess.run([sys.executable, '-B', '-c', code], cwd=root, env=environment,
        capture_output=True, timeout=60, check=False)
    assert result.returncode == 0, result.stderr.decode()
