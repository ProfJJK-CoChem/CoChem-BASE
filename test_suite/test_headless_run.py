from __future__ import annotations
import os

from pathlib import Path

import pytest

import headless_run


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_resolve_artifact_path_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('COCHEM_ARTIFACT_DIR', raising=False)
    resolved = headless_run.resolve_artifact_path(None)
    assert resolved == (Path.home() / 'CoChem_Artifacts').resolve()


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_resolve_artifact_path_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    custom_dir = str(tmp_path / 'custom_artifacts')
    monkeypatch.setenv('COCHEM_ARTIFACT_DIR', custom_dir)
    resolved = headless_run.resolve_artifact_path(None)
    assert resolved == Path(custom_dir).resolve()


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_resolve_artifact_path_explicit_str(tmp_path: Path) -> None:
    explicit = tmp_path / 'explicit_dir'
    resolved = headless_run.resolve_artifact_path(str(explicit))
    assert resolved == explicit.resolve()


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_resolve_artifact_path_explicit_path(tmp_path: Path) -> None:
    explicit = tmp_path / 'explicit_path_obj'
    resolved = headless_run.resolve_artifact_path(explicit)
    assert resolved == explicit.resolve()


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_resolve_artifact_path_tilde(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    monkeypatch.setenv('HOME', str(tmp_path))
    resolved = headless_run.resolve_artifact_path('~/test_silo')
    assert resolved == (tmp_path / 'test_silo').resolve()


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_resolve_artifact_path_env_vars(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv('MY_TEST_BASE_DIR', str(tmp_path / 'env_expanded'))
    resolved = headless_run.resolve_artifact_path('$MY_TEST_BASE_DIR/artifacts')
    assert resolved == (tmp_path / 'env_expanded' / 'artifacts').resolve()


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_get_interface_and_calc_env_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
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


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_get_interface_and_calc_env_codespaces(monkeypatch: pytest.MonkeyPatch) -> None:
    iface, calc = headless_run.get_interface_and_calc_env()
    assert iface == 'Codespaces'
    assert calc == 'GitHub Actions'


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_configure_execution_environment_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('ORCA_CMD', 'test_orca_path')
    monkeypatch.setenv('MPI_CMD', 'test_mpi_path')
    config = headless_run.configure_execution_environment()
    assert 'COCHEM_INTERFACE_ENV' in config
    assert 'COCHEM_CALC_ENV' in config
    assert config['ORCA_CMD'] == 'test_orca_path'
    assert config['MPI_CMD'] == 'test_mpi_path'


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_configure_execution_environment_explicit(tmp_path: Path) -> None:
    orca_bin = tmp_path / 'orca'
    mpi_bin = tmp_path / 'mpirun'
    config = headless_run.configure_execution_environment(
        orca_cmd=str(orca_bin),
        mpi_cmd=str(mpi_bin),
    )
    assert Path(config['ORCA_CMD']) == orca_bin.resolve()
    assert Path(config['MPI_CMD']) == mpi_bin.resolve()


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_provision_cochem_environment_existing(tmp_path: Path) -> None:
    """Verify provision_cochem_environment accurately detects pre-existing Conda silo."""
    target = tmp_path / 'test_env_exist'
    meta_dir = target / 'Silos' / 'cochem_base_silo' / 'conda-meta'
    meta_dir.mkdir(parents=True, exist_ok=True)
    (meta_dir / 'history.json').write_text('{"packages": []}', encoding="utf-8")

    success, env_dir, already = headless_run.provision_cochem_environment(
        artifact_path=str(target),
        clean_silo=False,
    )
    assert success is True
    assert env_dir == target / 'Silos' / 'cochem_base_silo'
    assert already is True


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_run_preflight_suite_live(tmp_path: Path) -> None:
    """Verify live preflight test suite execution returns structured results."""
    mod_dir = tmp_path / 'modules'
    mod_dir.mkdir(parents=True, exist_ok=True)
    all_passed, results = headless_run.run_preflight_suite(
        module_dir=mod_dir,
        orca_path=str(tmp_path / 'orca'),
        mpi_path=str(tmp_path / 'mpirun'),
    )
    assert isinstance(all_passed, bool)
    assert results is not None


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_run_preflight_suite_custom_args(tmp_path: Path) -> None:
    """Verify preflight suite handles custom path arguments cleanly."""
    custom_mod = tmp_path / 'custom_modules'
    custom_mod.mkdir(parents=True, exist_ok=True)
    all_passed, results = headless_run.run_preflight_suite(
        module_dir=custom_mod,
        orca_path=str(tmp_path / 'opt' / 'orca'),
        mpi_path=str(tmp_path / 'opt' / 'mpirun'),
    )
    assert isinstance(all_passed, bool)
    assert results is not None


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_main_cli_skip_all() -> None:
    """Verify CLI entrypoint succeeds when tasks are flagged as skipped."""
    exit_code = headless_run.main(['--skip-provision', '--skip-tests'])
    assert exit_code == 0


@pytest.mark.skipif(os.environ.get("CODESPACES") != "true", reason="Requires CODESPACES=true")
def test_main_cli_with_artifact_dir(tmp_path: Path) -> None:
    """Verify CLI entrypoint configures artifact directory safely."""
    target = tmp_path / 'cli_artifacts'
    exit_code = headless_run.main([
        '--artifact-dir', str(target),
        '--skip-provision',
        '--skip-tests',
    ])
    assert exit_code == 0

