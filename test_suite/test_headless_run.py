from __future__ import annotations

from pathlib import Path

import pytest

import headless_run
from test_suite.run_tests import PreflightCheckResult, TestResult


def test_resolve_artifact_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('COCHEM_ARTIFACT_DIR', raising=False)
    resolved = headless_run.resolve_artifact_path(None)
    assert resolved == (Path.home() / 'CoChem_Artifacts').resolve()


def test_resolve_artifact_path_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom_dir = str(tmp_path / 'custom_artifacts')
    monkeypatch.setenv('COCHEM_ARTIFACT_DIR', custom_dir)
    resolved = headless_run.resolve_artifact_path(None)
    assert resolved == Path(custom_dir).resolve()


def test_resolve_artifact_path_explicit_str(tmp_path: Path) -> None:
    explicit = tmp_path / 'explicit_dir'
    resolved = headless_run.resolve_artifact_path(str(explicit))
    assert resolved == explicit.resolve()


def test_resolve_artifact_path_explicit_path(tmp_path: Path) -> None:
    explicit = tmp_path / 'explicit_path_obj'
    resolved = headless_run.resolve_artifact_path(explicit)
    assert resolved == explicit.resolve()


def test_resolve_artifact_path_tilde(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    monkeypatch.setenv('HOME', str(tmp_path))
    resolved = headless_run.resolve_artifact_path('~/test_silo')
    assert resolved == (tmp_path / 'test_silo').resolve()


def test_resolve_artifact_path_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('MY_TEST_BASE_DIR', str(tmp_path / 'env_expanded'))
    resolved = headless_run.resolve_artifact_path('$MY_TEST_BASE_DIR/artifacts')
    assert resolved == (tmp_path / 'env_expanded' / 'artifacts').resolve()


def test_get_interface_and_calc_env_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('CODESPACES', raising=False)

    monkeypatch.setattr('platform.system', lambda: 'Windows')
    iface, calc = headless_run.get_interface_and_calc_env()
    assert iface == 'Local-Windows (WSL)'
    assert calc == 'Local-Windows (WSL)'

    monkeypatch.setattr('platform.system', lambda: 'Darwin')
    iface, calc = headless_run.get_interface_and_calc_env()
    assert iface == 'Local-MacOS (OrbStack)'
    assert calc == 'Local-MacOS (OrbStack)'

    monkeypatch.setattr('platform.system', lambda: 'Linux')
    iface, calc = headless_run.get_interface_and_calc_env()
    assert iface == 'Local-Linux (Deb)'
    assert calc == 'Local-Linux (Deb)'

    monkeypatch.setattr('platform.system', lambda: 'UnknownOS')
    iface, calc = headless_run.get_interface_and_calc_env()
    assert iface == 'Codespaces'
    assert calc == 'GitHub Actions'


def test_get_interface_and_calc_env_codespaces(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('CODESPACES', 'true')
    iface, calc = headless_run.get_interface_and_calc_env()
    assert iface == 'Codespaces'
    assert calc == 'GitHub Actions'


def test_configure_execution_environment_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ORCA_CMD', 'test_orca_path')
    monkeypatch.setenv('MPI_CMD', 'test_mpi_path')
    config = headless_run.configure_execution_environment()
    assert 'COCHEM_INTERFACE_ENV' in config
    assert 'COCHEM_CALC_ENV' in config
    assert config['ORCA_CMD'] == 'test_orca_path'
    assert config['MPI_CMD'] == 'test_mpi_path'


def test_configure_execution_environment_explicit(tmp_path: Path) -> None:
    orca_bin = tmp_path / 'orca'
    mpi_bin = tmp_path / 'mpirun'
    config = headless_run.configure_execution_environment(
        orca_cmd=str(orca_bin),
        mpi_cmd=str(mpi_bin),
    )
    assert Path(config['ORCA_CMD']) == orca_bin.resolve()
    assert Path(config['MPI_CMD']) == mpi_bin.resolve()


def test_provision_cochem_environment_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / 'test_env'
    silo_target = target / 'Silos' / 'cochem_base_silo'

    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (True, silo_target, False))
    success, env_dir, already = headless_run.provision_cochem_environment(
        artifact_path=str(target),
        clean_silo=True,
    )
    assert success is True
    assert env_dir == silo_target
    assert already is False
    assert (target / 'Silos').exists()


def test_provision_cochem_environment_no_clean_existing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / 'test_env_noclean'
    silo_dir = target / 'Silos'
    silo_dir.mkdir(parents=True, exist_ok=True)
    sentinel_file = silo_dir / 'sentinel.txt'
    sentinel_file.write_text('keep_me')
    silo_target = silo_dir / 'cochem_base_silo'

    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (True, silo_target, True))
    success, env_dir, already = headless_run.provision_cochem_environment(
        artifact_path=str(target),
        clean_silo=False,
    )
    assert success is True
    assert env_dir == silo_target
    assert already is True
    assert sentinel_file.exists()


def test_provision_cochem_environment_backend_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / 'test_env_fail'
    silo_target = target / 'Silos' / 'cochem_base_silo'
    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (False, silo_target, False))
    success, env_dir, already = headless_run.provision_cochem_environment(artifact_path=str(target))
    assert success is False
    assert env_dir == silo_target
    assert already is False


def test_provision_cochem_environment_exception(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / 'test_env_exception'
    def trigger_provisioning_error(*a, **kw):
        msg = 'Provision failed'
        if len(msg) > 0:
            raise ValueError(msg)
        return (False, target, False)
    monkeypatch.setattr('headless_run.provision_silo', trigger_provisioning_error)
    with pytest.raises(ValueError, match='EXCEPTION_DEFLECTION_BLOCKED'):
        headless_run.provision_cochem_environment(artifact_path=str(target))


def _build_passing_preflight_result() -> PreflightCheckResult:
    return PreflightCheckResult(
        silo=TestResult(status=True, message='OK'),
        artifacts=TestResult(status=True, message='OK'),
        modules=TestResult(status=True, message='OK'),
        orca_single=TestResult(status=True, message='OK'),
        orca_mpi=TestResult(status=True, message='OK'),
    )


def _build_failing_preflight_result() -> PreflightCheckResult:
    return PreflightCheckResult(
        silo=TestResult(status=True, message='OK'),
        artifacts=TestResult(status=False, message='Failed component'),
        modules=TestResult(status=True, message='OK'),
        orca_single=TestResult(status=True, message='OK'),
        orca_mpi=TestResult(status=True, message='OK'),
    )


def test_run_preflight_suite_all_pass(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', lambda **kw: _build_passing_preflight_result())
    all_passed, results = headless_run.run_preflight_suite(module_dir='.', orca_path='orca', mpi_path='mpirun')
    assert all_passed is True
    assert results is not None


def test_run_preflight_suite_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', lambda **kw: _build_failing_preflight_result())
    all_passed, results = headless_run.run_preflight_suite(module_dir='.', orca_path='orca', mpi_path='mpirun')
    assert all_passed is False


def test_run_preflight_suite_custom_args(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []
    def record_preflight_invocation(**kw):
        calls.append(kw)
        return _build_passing_preflight_result()
    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', record_preflight_invocation)
    all_passed, _ = headless_run.run_preflight_suite(
        module_dir=Path('/custom/modules'),
        orca_path='/opt/orca/orca',
        mpi_path='/opt/openmpi/bin/mpirun',
    )
    assert all_passed is True
    assert len(calls) == 1
    assert calls[0] == dict(
        module_dir=str(Path('/custom/modules')),
        orca_path='/opt/orca/orca',
        mpi_path='/opt/openmpi/bin/mpirun',
    )


def test_run_preflight_suite_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def trigger_test_error(**kw):
        msg = 'Execution failed'
        if len(msg) > 0:
            raise OSError(msg)
        return _build_passing_preflight_result()
    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', trigger_test_error)
    with pytest.raises(ValueError, match='EXCEPTION_DEFLECTION_BLOCKED'):
        headless_run.run_preflight_suite(module_dir='.', orca_path='orca', mpi_path='mpirun')


def test_main_cli_skip_all() -> None:
    exit_code = headless_run.main(['--skip-provision', '--skip-tests'])
    assert exit_code == 0


def test_main_cli_execution_pass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / 'cli_artifacts'
    silo_target = target / 'Silos' / 'cochem_base_silo'

    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (True, silo_target, True))
    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', lambda **kw: _build_passing_preflight_result())
    exit_code = headless_run.main(['--artifact-dir', str(target), '--clean'])
    assert exit_code == 0


def test_main_cli_execution_fail_provision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / 'cli_artifacts_fail_prov'
    silo_target = target / 'Silos' / 'cochem_base_silo'

    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (False, silo_target, False))
    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', lambda **kw: _build_passing_preflight_result())
    exit_code = headless_run.main(['--artifact-dir', str(target)])
    assert exit_code == 1


def test_main_cli_execution_fail_preflight(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / 'cli_artifacts_fail_test'
    silo_target = target / 'Silos' / 'cochem_base_silo'

    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (True, silo_target, True))
    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', lambda **kw: _build_failing_preflight_result())
    exit_code = headless_run.main([
        '--artifact-dir', str(target),
        '--module-dir', str(tmp_path / 'modules'),
        '--orca-cmd', '/custom/orca',
        '--mpi-cmd', '/custom/mpirun',
    ])
    assert exit_code == 1

