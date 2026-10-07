"""Exercise real widgets and request validation with licensed authority absent."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('case', ['missing', 'free', 'remote', 'cfour-contract', 'remote-cfour'])
def test_optional_engine_controls_in_isolated_process(tmp_path, case):
    environment = dict(os.environ, COCHEM_CONFIG=str(tmp_path / 'absent-registry.json'),
                       COCHEM_ARTIFACT_DIR=str(tmp_path / 'artifacts'))
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), case], env=environment,
        capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _exercise(case: str) -> None:
    from traitlets import TraitError
    from ui.voila_layout.cochem_gui import CoChemGUI, licensed_engine_availability

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
    if case not in {'remote', 'remote-cfour'}:
        raise ValueError('Unknown optional engine control case')
    gui.calc_env_dropdown.value = 'github-actions'
    assert gui.matrix_engine.value == 'ORCA'
    assert 'Remote licensed-engine availability is unverified' in gui.licensed_engine_status.value
    gui.gh_repo_input.value = 'course-organization/student-water'
    gui.product_class_selector.value = 'Screening (no product accuracy claim)'
    gui.matrix_tier.value = 'T2'
    gui.matrix_method.value = 'HF/STO-3G'
    gui.matrix_basis.value = 'STO-3G'
    gui.matrix_solvation.value = None
    if case == 'remote-cfour':
        gui.matrix_engine.value = 'CFOUR'
        assert gui.matrix_tier.options == ('T2', 'T6', 'T8')
        assert gui.matrix_solvation.disabled and gui.cb_recipe_r1.disabled and gui.cb_recipe_r2.disabled
        assert 'CFOUR_Actions_Setup.md' in gui.gh_guidance.value
        assert gui.matrix_method.value == 'HF' and gui.matrix_basis.value == 'cc-pVDZ'
        assert not any(basis.startswith('def2-') for basis in gui.matrix_basis.options)
        for operation, optimize, frequencies in (
                ('single_point', False, False), ('optimization', True, False),
                ('harmonic_frequencies', False, True), ('optimization_frequencies', True, True)):
            gui.actions_operation.value = operation
            gui._prepare_actions_job()
            config = gui._last_actions_job['config']
            assert config['engine'] == 'cfour' and config['method'] == 'HF'
            assert config['is_opt'] is optimize and config['is_freq'] is frequencies
            assert config['initial_hessian'] == ('BFGS' if optimize else 'XTB2')
            assert config['grid_stage'] is None and config['theory_tier'] is None
            assert config['timeout_seconds'] == 300
        assert gui._last_actions_job['job_file'].endswith('-cfour-job.json')
        assert 'actions/workflows/cfour_calculation.yml' in gui.actions_job_download.value
        assert 'Download CFOUR job JSON' in gui.actions_job_download.value
        assert 'No calculation has been submitted or run' in gui.actions_job_download.value
        gui.matrix_tier.value = 'T8'
        gui.matrix_method.value = 'CCSD(T)'
        assert gui.actions_operation.options == (('Single point', 'single_point'),)
        with pytest.raises(TraitError):
            gui.actions_operation.value = 'optimization'
        gui._prepare_actions_job()
        assert gui._last_actions_job['config']['method'] == 'CCSD(T)'
        gui.multiplicity_input.value = 3
        assert gui.btn_execute.disabled
        gui._prepare_actions_job()
        assert gui._last_actions_job is None
        assert not gui._pipeline_running and not hasattr(gui, '_pipeline_worker')
        gui.calc_env_dropdown.value = 'linux'
        assert gui.matrix_engine.value is None and gui.matrix_method.disabled
        return
    gui._prepare_actions_job()
    assert gui._last_actions_job['config']['engine'] == 'orca'
    assert 'No calculation has been submitted or run' in gui.actions_job_download.value
    assert not gui._pipeline_running and not hasattr(gui, '_pipeline_worker')
    gui.calc_env_dropdown.value = 'linux'
    assert gui.matrix_engine.value is None
    assert gui.matrix_method.disabled and gui.btn_execute.disabled
    assert gui._last_actions_job is None


if __name__ == '__main__':
    _exercise(sys.argv[1])
