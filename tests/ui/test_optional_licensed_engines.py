"""Exercise real widgets and request validation with licensed authority absent."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from ci_tools.source_quarantine import source_paths


@pytest.mark.parametrize('case', ['missing', 'free', 'remote', 'cfour-contract', 'remote-cfour', 'catalog-transitions', 'remote-auth-failure', 'withdrawal-state-controls'])
def test_optional_engine_controls_in_isolated_process(tmp_path, case):
    environment = dict(os.environ, COCHEM_CONFIG=str(tmp_path / 'absent-registry.json'),
                       COCHEM_ARTIFACT_DIR=str(tmp_path / 'artifacts'))
    source = Path(__file__).resolve().parents[2]
    environment['PYTHONPATH'] = os.pathsep.join(source_paths(source))
    environment['COCHEM_STUDENT_AUTO_REMOTE_CHECK'] = '0'
    if case == 'remote-auth-failure':
        # A genuinely unauthenticated process, without a replacement GitHub API
        # or fabricated engine/readiness responses.
        environment.pop('GH_TOKEN', None)
        environment.pop('GITHUB_TOKEN', None)
        environment['PATH'] = str(tmp_path / 'no-credential-helper')
        environment['COCHEM_STUDENT_AUTO_REMOTE_CHECK'] = '0'
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), case], env=environment,
        capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _exercise(case: str) -> None:
    source = Path(__file__).resolve().parents[2]
    if os.environ.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
        # Assert startup already enforced the inherited profile boundary;
        # importing/activating quarantine here would conceal a missing shim.
        startup = sys.modules.get('sitecustomize')
        assert startup is not None
        assert Path(startup.__file__).resolve() == source / 'ci_tools/quarantine_startup/sitecustomize.py'
        quarantine = sys.modules.get('ci_tools.source_quarantine')
        state = getattr(quarantine, '_active', None)
        assert state is not None and state['copied'] == source
        assert str(state['original']) == os.environ['COCHEM_SOURCE_QUARANTINE_ORIGINAL']
    from traitlets import TraitError
    from ui.voila_layout.cochem_gui import CoChemGUI, licensed_engine_availability
    import ui.voila_layout.cochem_gui as gui_module

    assert Path(gui_module.__file__).resolve() == Path(__file__).resolve().parents[2] / 'ui/voila_layout/cochem_gui.py'

    gui = CoChemGUI()
    available = licensed_engine_availability()
    assert set(available) == {'orca', 'cfour'}
    assert all(not observation['available'] and observation['reason'] for observation in available.values())
    assert {'ORCA', 'CFOUR'}.isdisjoint(value for _, value in gui.matrix_engine.options)
    assert gui.matrix_engine.value is None
    assert gui.matrix_method.disabled and gui.matrix_basis.disabled
    assert gui.matrix_tier.disabled and gui.cfour_operation.disabled
    assert gui.btn_execute.disabled
    assert 'optional and strongly recommended' in gui.licensed_engine_status.value
    assert 'Installation Error' != gui.state.system_status
    for engine in ('ORCA', 'CFOUR'):
        with pytest.raises(TraitError):
            gui.matrix_engine.value = engine
    for view in ('matrix', 'inspector', 'modules'):
        gui.state.active_view = view
        assert gui.main_content.children
    gui.license_mode.value = 'cfour'
    assert gui.license_mode.value == 'cfour'
    assert not gui.license_mode.disabled
    geometry = Path(__file__).resolve().parents[2].joinpath('examples/jobs/water.xyz').read_text(encoding='utf-8')
    gui.matrix_geometry.value = geometry
    if case == 'withdrawal-state-controls':
        # Synthetic prior widget state tests admission only. It is not a live
        # GitHub readiness receipt or proof of these scientific capabilities.
        for name in ('_research_capability_worker', '_student_setup_initial_worker'):
            worker = getattr(gui, name, None)
            if worker is not None:
                worker.join(timeout=15)
                assert not worker.is_alive()
        target = ('course-organization/student-water', 'main')
        gui.calc_env_dropdown.value = 'github-actions'
        gui.gh_repo_input.value = target[0]
        gui.gh_branch_input.value = target[1]
        gui._remote_engine_target = target
        gui._remote_engine_availability = {engine: {'status': 'available', 'provisionable': True,
            'reason': 'Synthetic prior state for control regression; no external readiness claim.'}
            for engine in ('orca', 'cfour')}
        gui._research_capability_observations = {
            'topos': {'module_id': 'topos', 'operations': ['energy', 'matrix']},
            'torq': {'module_id': 'torq', 'operations': ['nbo_analysis'], 'provider_capabilities': {
                'scientific_apis': {'nbo_analysis': {'available': True, 'supported_engines': ['orca', 'pyscf']}}}}}
        gui.research_topos_operation.options = [('Synthetic state admission only', 'energy'),
            ('Synthetic matrix admission only', 'matrix')]
        gui._refresh_engine_choices()
        gui._refresh_research_engine_choices()
        gui._refresh_orbital_backend_choices()
        gui.research_topos_operation.value = 'energy'
        assert gui._actions_admission_checked != target
        gui._refresh_execution_gate()
        assert gui.btn_research_topos.disabled  # Unchecked project admission is independently required.
        assert not (gui._pipeline_running or gui._hpc_running or gui._hpc_retrieving
                    or gui._actions_running or gui._actions_state_operation is not None
                    or gui._topos_running or gui._student_setup_busy)
        # Synthetic prior checked-target UI state only, like the prior licensed
        # observations above; not an actual GitHub check, capability or readiness receipt.
        gui._actions_admission_checked = target
        gui._refresh_execution_gate()
        assert not gui.btn_research_topos.disabled
        gui.matrix_engine.value = 'ORCA'
        gui.research_topos_engine.value = 'orca'
        gui.research_orbital_backend.value = 'orca'
        gui._withdraw_remote_engine_access(target)
        assert gui.matrix_engine.value is None and gui.btn_execute.disabled, (
            gui.matrix_engine.value, gui.btn_execute.disabled, gui.gh_repo_input.value,
            gui.gh_branch_input.value, gui._remote_engine_availability)
        assert gui.research_topos_engine.value is None and gui.btn_research_topos.disabled
        assert gui.research_orbital_backend.value is None and gui.btn_research_nbo.disabled
        assert 'orca' not in dict(gui.research_topos_engine.options).values()
        assert 'orca' not in dict(gui.research_orbital_backend.options).values()
        gui._run_student_topos()
        assert 'Choose an available research method' in gui.research_status.value
        assert not gui._pipeline_running and not gui._actions_running
        gui._refresh_research_engine_choices()
        assert gui.research_topos_engine.value is None  # Repeated refresh cannot choose xTB silently.
        for message in ('Authentication unavailable', 'The remote engine check exceeded 20 minutes; cancellation was requested.'):
            gui._render_remote_engine_check_failure(target, message)
            assert message in gui.remote_engine_status.value
            assert gui.matrix_engine.value is None
        gui.matrix_engine.value = 'XTB'
        gui.research_topos_engine.value = 'xtb'
        gui.research_orbital_backend.value = 'pyscf'
        method = gui.matrix_method.value
        gui._withdraw_remote_engine_access(target)
        assert gui.matrix_engine.value == 'XTB' and gui.matrix_method.value == method
        assert gui.research_topos_engine.value == 'xtb'
        assert gui.research_orbital_backend.value == 'pyscf'
        assert not gui.btn_research_topos.disabled
        gui.research_topos_operation.value = 'matrix'
        assert gui.research_matrix_recipe.value == '' and gui.btn_research_topos.disabled
        gui.research_topos_operation.value = 'energy'
        assert not gui.btn_research_topos.disabled
        gui._apply_student_engine_diagnostics({'failure_category': 'engine_provisioning',
            'engine_availability': {'orca': {'status': 'available', 'provisionable': True}}},
            {'repository': target[0], 'branch': target[1]})
        assert not gui._remote_engine_availability['orca']['provisionable']
        gui.gh_repo_input.value = 'course-organization/another-student'
        guidance = gui.remote_engine_status.value
        observations = gui._remote_engine_availability
        gui._render_remote_engine_check_failure(target, 'Delayed failure for the earlier project')
        gui._withdraw_remote_engine_access(target)
        assert gui.remote_engine_status.value == guidance
        assert gui._remote_engine_availability is observations
        return
    if case == 'remote-auth-failure':
        from datetime import datetime, timezone
        import hashlib

        original = geometry.encode('utf-8')
        gui.xyz_upload.value = ({'name': 'retained-water.xyz', 'type': 'chemical/x-xyz',
            'size': len(original), 'content': memoryview(original),
            'last_modified': datetime.now(timezone.utc)},)
        selected = gui.student_geometry_choice.value
        retained = Path(gui._student_uploads[selected]['path'])
        digest = hashlib.sha256(retained.read_bytes()).hexdigest()
        gui.calc_env_dropdown.value = 'github-actions'
        gui.gh_repo_input.value = 'course-organization/student-water'
        gui.matrix_engine.value = 'XTB'
        method = gui.matrix_method.value
        for _ in range(2):
            previous_observations = gui._remote_engine_availability
            gui.btn_remote_engine_check.click()
            gui._remote_probe_worker.join(timeout=10)
            assert not gui._remote_probe_worker.is_alive()
            assert gui._remote_engine_availability is not previous_observations
            assert all(not item['provisionable'] for item in gui._remote_engine_availability.values())
            assert 'GitHub authentication is unavailable' in gui.remote_engine_status.value
            assert 'Check ORCA &amp; CFOUR' in gui.remote_engine_status.value
            assert not gui.btn_remote_engine_check.disabled
            assert gui.btn_remote_engine_cancel.disabled
            assert not gui._remote_probe_running
            assert gui.matrix_engine.value == 'XTB' and gui.matrix_method.value == method
            assert {'ORCA', 'CFOUR'}.isdisjoint(value for _, value in gui.matrix_engine.options)
            assert gui.student_geometry_choice.value == selected
            assert hashlib.sha256(retained.read_bytes()).hexdigest() == digest
            assert gui.matrix_geometry.value.encode('utf-8') == original
        gui.gh_repo_input.value = 'course-organization/another-student'
        assert 'could not be checked' not in gui.remote_engine_status.value
        assert all(not item['provisionable'] for item in gui._remote_engine_availability.values())
        gui._prepare_actions_job()
        assert gui._last_actions_job['config']['engine'] == 'xtb'
        assert 'No calculation has been submitted or run' in gui.actions_job_download.value
        assert not gui._pipeline_running and not gui._actions_running
        return
    if case == 'missing':
        gui._execute_pipeline(None)
        assert not gui._pipeline_running
        assert not hasattr(gui, '_pipeline_worker')
        return
    if case == 'free':
        for engine, method, tier in (('XTB', 'GFN2-xTB', 'T1'), ('PYSCF', 'HF', 'T2')):
            gui.matrix_engine.value = engine
            config = gui._collect_run_config()
            assert config['engine'] == engine.lower() and config['method'] == method
            assert config['theory_tier'] == tier and config['product_class'] is None
            assert not config['implicit_solvation']
            assert gui.matrix_tier.options == (tier,)
            assert gui.cb_recipe_r1.disabled and gui.cb_recipe_r2.disabled
            assert gui.btn_execute.disabled  # The free engine also needs its own execution authority.
        return
    if case == 'cfour-contract':
        from cochem_base.exceptions import MethodologyViolationError

        # Exercise serialization without granting a binary execution authority
        # or enabling the disabled licensed controls in the displayed widgets.
        gui.product_class_selector.value = 'Screening (no product accuracy claim)'
        gui.matrix_tier.value = 'T2'
        gui.matrix_method.value = 'HF/STO-3G'
        gui.matrix_basis.value = 'STO-3G'
        gui.matrix_solvation.value = None
        gui.cb_recipe_r1.value = False
        for operation, optimize, frequencies in (
                ('single_point', False, False), ('optimization', True, False),
                ('harmonic_frequencies', False, True), ('optimization_frequencies', True, True)):
            gui.cfour_operation.value = operation
            config = gui._cfour_run_config()
            assert config['engine'] == 'cfour' and config['method'] == 'HF'
            assert config['is_opt'] is optimize and config['is_freq'] is frequencies
            assert config['is_vpt2'] is False and config['product_class'] is None
            assert config['theory_tier'] is None and config['grid_stage'] is None
            assert config['initial_hessian'] == ('BFGS' if optimize else 'XTB2')
        gui.cfour_operation.value = 'single_point'
        gui.multiplicity_input.value = 3
        with pytest.raises(MethodologyViolationError, match='unavailable'):
            gui._cfour_run_config()
        assert gui.matrix_engine.value is None and gui.cfour_operation.disabled
        return
    if case not in {'remote', 'remote-cfour', 'catalog-transitions'}:
        raise ValueError('Unknown optional engine control case')
    gui.calc_env_dropdown.value = 'github-actions'
    gui.gh_repo_input.value = 'course-organization/student-water'
    assert gui.matrix_engine.value is None
    assert {'ORCA', 'CFOUR'}.isdisjoint(value for _, value in gui.matrix_engine.options)
    assert all(not item['provisionable'] for item in gui._remote_engine_availability.values())
    assert 'CFOUR_Actions_Setup.md' in gui.gh_guidance.value
    assert gui.btn_execute.disabled
    for engine in ('ORCA', 'CFOUR'):
        with pytest.raises(TraitError):
            gui.matrix_engine.value = engine
    gui.matrix_engine.value = 'XTB'
    assert gui.actions_operation.options == (('Geometry optimization', 'optimization'),)
    gui._prepare_actions_job()
    assert gui._last_actions_job['config']['engine'] == 'xtb'
    assert gui._last_actions_job['config']['is_opt'] is True
    assert not gui._pipeline_running and not hasattr(gui, '_pipeline_worker')
    assert 'No calculation has been submitted or run' in gui.actions_job_download.value
    gui.gh_repo_input.value = 'course-organization/other-student'
    assert gui._last_actions_job is None
    assert {'ORCA', 'CFOUR'}.isdisjoint(value for _, value in gui.matrix_engine.options)
    gui.calc_env_dropdown.value = 'linux'
    assert gui.matrix_engine.value == 'XTB'
    assert gui.btn_execute.disabled  # The local host still needs actual Stage 0 authority.
    if case == 'catalog-transitions':
        gui.matrix_engine.value = 'PYSCF'
        config = gui._collect_run_config()
        assert config['engine'] == 'pyscf' and config['method'] == 'HF'
        assert gui.matrix_tier.options == ('T2',)
        gui.calc_env_dropdown.value = 'github-actions'
        assert gui.matrix_engine.value is None
        assert gui.matrix_method.disabled and gui.btn_execute.disabled


if __name__ == '__main__':
    _exercise(sys.argv[1])
