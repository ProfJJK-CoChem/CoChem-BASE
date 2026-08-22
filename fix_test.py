import re
from pathlib import Path

path = Path(r"D:\__CoChem\GitHub-Repo\CoChem-BASE\test_suite\test_headless_run.py")
content = path.read_text(encoding="utf-8")

# Remove mock import
content = re.sub(r'from unittest\.mock import patch\n?', '', content)

# 1. get_interface_and_calc_env_platforms
content = content.replace(
    "    with patch('platform.system', return_value='Windows'):\n        iface, calc = headless_run.get_interface_and_calc_env()\n        assert iface == 'Local-Windows (WSL)'\n        assert calc == 'Local-Windows (WSL)'",
    "    monkeypatch.setattr('platform.system', lambda: 'Windows')\n    iface, calc = headless_run.get_interface_and_calc_env()\n    assert iface == 'Local-Windows (WSL)'\n    assert calc == 'Local-Windows (WSL)'"
)
content = content.replace(
    "    with patch('platform.system', return_value='Darwin'):\n        iface, calc = headless_run.get_interface_and_calc_env()\n        assert iface == 'Local-MacOS (OrbStack)'\n        assert calc == 'Local-MacOS (OrbStack)'",
    "    monkeypatch.setattr('platform.system', lambda: 'Darwin')\n    iface, calc = headless_run.get_interface_and_calc_env()\n    assert iface == 'Local-MacOS (OrbStack)'\n    assert calc == 'Local-MacOS (OrbStack)'"
)
content = content.replace(
    "    with patch('platform.system', return_value='Linux'):\n        iface, calc = headless_run.get_interface_and_calc_env()\n        assert iface == 'Local-Linux (Deb)'\n        assert calc == 'Local-Linux (Deb)'",
    "    monkeypatch.setattr('platform.system', lambda: 'Linux')\n    iface, calc = headless_run.get_interface_and_calc_env()\n    assert iface == 'Local-Linux (Deb)'\n    assert calc == 'Local-Linux (Deb)'"
)
content = content.replace(
    "    with patch('platform.system', return_value='UnknownOS'):\n        iface, calc = headless_run.get_interface_and_calc_env()\n        assert iface == 'Codespaces'\n        assert calc == 'GitHub Actions'",
    "    monkeypatch.setattr('platform.system', lambda: 'UnknownOS')\n    iface, calc = headless_run.get_interface_and_calc_env()\n    assert iface == 'Codespaces'\n    assert calc == 'GitHub Actions'"
)

# 2. provision_cochem_environment_success
content = re.sub(
    r"    with patch\('headless_run\.provision_silo', return_value=\(True, silo_target, False\)\):\n\s+(success, env_dir, already = headless_run\.provision_cochem_environment\()",
    r"    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (True, silo_target, False))\n    \1",
    content
)
# Fix assert indents
content = content.replace("            artifact_path=str(target),\n            clean_silo=True,\n        )\n        assert success is True\n        assert env_dir == silo_target\n        assert already is False\n        assert (target / 'Silos').exists()",
"        artifact_path=str(target),\n        clean_silo=True,\n    )\n    assert success is True\n    assert env_dir == silo_target\n    assert already is False\n    assert (target / 'Silos').exists()")

# 3. test_provision_cochem_environment_no_clean_existing
content = re.sub(
    r"    with patch\('headless_run\.provision_silo', return_value=\(True, silo_target, True\)\):\n\s+(success, env_dir, already = headless_run\.provision_cochem_environment\()",
    r"    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (True, silo_target, True))\n    \1",
    content
)
content = content.replace("            artifact_path=str(target),\n            clean_silo=False,\n        )\n        assert success is True\n        assert env_dir == silo_target\n        assert already is True\n        assert sentinel_file.exists()",
"        artifact_path=str(target),\n        clean_silo=False,\n    )\n    assert success is True\n    assert env_dir == silo_target\n    assert already is True\n    assert sentinel_file.exists()")

# 4. test_provision_cochem_environment_backend_failure
content = re.sub(
    r"    with patch\('headless_run\.provision_silo', return_value=\(False, silo_target, False\)\):\n\s+(success, env_dir, already = headless_run\.provision_cochem_environment\(artifact_path=str\(target\)\))\n\s+assert success is False\n\s+assert env_dir == silo_target\n\s+assert already is False",
    r"    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (False, silo_target, False))\n    \1\n    assert success is False\n    assert env_dir == silo_target\n    assert already is False",
    content
)

# 5. test_provision_cochem_environment_exception
content = re.sub(
    r"    with patch\('headless_run\.provision_silo', side_effect=RuntimeError\('Provision failed'\)\):\n\s+with pytest\.raises\(ValueError, match='EXCEPTION_DEFLECTION_BLOCKED'\):\n\s+(headless_run\.provision_cochem_environment\(artifact_path=str\(target\)\))",
    r"    def _fail(*a, **kw): raise RuntimeError('Provision failed')\n    monkeypatch.setattr('headless_run.provision_silo', _fail)\n    with pytest.raises(ValueError, match='EXCEPTION_DEFLECTION_BLOCKED'):\n        \1",
    content
)

# Add monkeypatch arg to provision functions
content = content.replace("def test_provision_cochem_environment_success(tmp_path: Path) -> None:", "def test_provision_cochem_environment_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:")
content = content.replace("def test_provision_cochem_environment_no_clean_existing(tmp_path: Path) -> None:", "def test_provision_cochem_environment_no_clean_existing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:")
content = content.replace("def test_provision_cochem_environment_backend_failure(tmp_path: Path) -> None:", "def test_provision_cochem_environment_backend_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:")
content = content.replace("def test_provision_cochem_environment_exception(tmp_path: Path) -> None:", "def test_provision_cochem_environment_exception(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:")

# 6. test_run_preflight_suite_all_pass
content = re.sub(
    r"def test_run_preflight_suite_all_pass\(\) -> None:\n\s+with patch\('test_suite\.run_tests\.run_all_preflight_checks', return_value=MockPreflightResult\(\)\):\n\s+(all_passed, results = headless_run\.run_preflight_suite\(module_dir='.', orca_path='orca', mpi_path='mpirun'\))\n\s+assert all_passed is True\n\s+assert results is not None",
    r"def test_run_preflight_suite_all_pass(monkeypatch: pytest.MonkeyPatch) -> None:\n    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', lambda **kw: MockPreflightResult())\n    \1\n    assert all_passed is True\n    assert results is not None",
    content
)

# 7. test_run_preflight_suite_failure
content = re.sub(
    r"def test_run_preflight_suite_failure\(\) -> None:\n\s+with patch\('test_suite\.run_tests\.run_all_preflight_checks', return_value=MockPreflightResultFail\(\)\):\n\s+(all_passed, results = headless_run\.run_preflight_suite\(module_dir='.', orca_path='orca', mpi_path='mpirun'\))\n\s+assert all_passed is False",
    r"def test_run_preflight_suite_failure(monkeypatch: pytest.MonkeyPatch) -> None:\n    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', lambda **kw: MockPreflightResultFail())\n    \1\n    assert all_passed is False",
    content
)

# 8. test_run_preflight_suite_custom_args
content = re.sub(
    r"def test_run_preflight_suite_custom_args\(\) -> None:\n\s+with patch\('test_suite\.run_tests\.run_all_preflight_checks', return_value=MockPreflightResult\(\)\) as mock_checks:\n\s+all_passed, _ = headless_run\.run_preflight_suite\(\n\s+module_dir=Path\('/custom/modules'\),\n\s+orca_path='/opt/orca/orca',\n\s+mpi_path='/opt/openmpi/bin/mpirun',\n\s+\)\n\s+assert all_passed is True\n\s+mock_checks\.assert_called_once_with\(\n\s+module_dir=str\(Path\('/custom/modules'\)\),\n\s+orca_path='/opt/orca/orca',\n\s+mpi_path='/opt/openmpi/bin/mpirun',\n\s+\)",
    r"def test_run_preflight_suite_custom_args(monkeypatch: pytest.MonkeyPatch) -> None:\n    calls = []\n    def _mock(**kw):\n        calls.append(kw)\n        return MockPreflightResult()\n    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', _mock)\n    all_passed, _ = headless_run.run_preflight_suite(\n        module_dir=Path('/custom/modules'),\n        orca_path='/opt/orca/orca',\n        mpi_path='/opt/openmpi/bin/mpirun',\n    )\n    assert all_passed is True\n    assert len(calls) == 1\n    assert calls[0] == dict(\n        module_dir=str(Path('/custom/modules')),\n        orca_path='/opt/orca/orca',\n        mpi_path='/opt/openmpi/bin/mpirun',\n    )",
    content
)

# 9. test_run_preflight_suite_exception
content = re.sub(
    r"def test_run_preflight_suite_exception\(\) -> None:\n\s+with patch\('test_suite\.run_tests\.run_all_preflight_checks', side_effect=OSError\('Execution failed'\)\):\n\s+with pytest\.raises\(ValueError, match='EXCEPTION_DEFLECTION_BLOCKED'\):\n\s+headless_run\.run_preflight_suite\(module_dir='.', orca_path='orca', mpi_path='mpirun'\)",
    r"def test_run_preflight_suite_exception(monkeypatch: pytest.MonkeyPatch) -> None:\n    def _fail(**kw): raise OSError('Execution failed')\n    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', _fail)\n    with pytest.raises(ValueError, match='EXCEPTION_DEFLECTION_BLOCKED'):\n        headless_run.run_preflight_suite(module_dir='.', orca_path='orca', mpi_path='mpirun')",
    content
)

# 10. test_main_cli_execution_pass
content = re.sub(
    r"def test_main_cli_execution_pass\(tmp_path: Path\) -> None:\n\s+target = tmp_path / 'cli_artifacts'\n\s+silo_target = target / 'Silos' / 'cochem_base_silo'\n\n\s+with patch\('headless_run\.provision_silo', return_value=\(True, silo_target, True\)\), \\\n\s+patch\('test_suite\.run_tests\.run_all_preflight_checks', return_value=MockPreflightResult\(\)\):\n\s+exit_code = headless_run\.main\(\['--artifact-dir', str\(target\), '--clean'\]\)\n\s+assert exit_code == 0",
    r"def test_main_cli_execution_pass(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:\n    target = tmp_path / 'cli_artifacts'\n    silo_target = target / 'Silos' / 'cochem_base_silo'\n\n    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (True, silo_target, True))\n    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', lambda **kw: MockPreflightResult())\n    exit_code = headless_run.main(['--artifact-dir', str(target), '--clean'])\n    assert exit_code == 0",
    content
)

# 11. test_main_cli_execution_fail_provision
content = re.sub(
    r"def test_main_cli_execution_fail_provision\(tmp_path: Path\) -> None:\n\s+target = tmp_path / 'cli_artifacts_fail_prov'\n\s+silo_target = target / 'Silos' / 'cochem_base_silo'\n\n\s+with patch\('headless_run\.provision_silo', return_value=\(False, silo_target, False\)\), \\\n\s+patch\('test_suite\.run_tests\.run_all_preflight_checks', return_value=MockPreflightResult\(\)\):\n\s+exit_code = headless_run\.main\(\['--artifact-dir', str\(target\)\]\)\n\s+assert exit_code == 1",
    r"def test_main_cli_execution_fail_provision(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:\n    target = tmp_path / 'cli_artifacts_fail_prov'\n    silo_target = target / 'Silos' / 'cochem_base_silo'\n\n    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (False, silo_target, False))\n    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', lambda **kw: MockPreflightResult())\n    exit_code = headless_run.main(['--artifact-dir', str(target)])\n    assert exit_code == 1",
    content
)

# 12. test_main_cli_execution_fail_preflight
content = re.sub(
    r"def test_main_cli_execution_fail_preflight\(tmp_path: Path\) -> None:\n\s+target = tmp_path / 'cli_artifacts_fail_test'\n\s+silo_target = target / 'Silos' / 'cochem_base_silo'\n\n\s+with patch\('headless_run\.provision_silo', return_value=\(True, silo_target, True\)\), \\\n\s+patch\('test_suite\.run_tests\.run_all_preflight_checks', return_value=MockPreflightResultFail\(\)\):\n\s+exit_code = headless_run\.main\(\[\n\s+'--artifact-dir', str\(target\),\n\s+'--module-dir', str\(tmp_path / 'modules'\),\n\s+'--orca-cmd', '/custom/orca',\n\s+'--mpi-cmd', '/custom/mpirun',\n\s+\]\)\n\s+assert exit_code == 1",
    r"def test_main_cli_execution_fail_preflight(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:\n    target = tmp_path / 'cli_artifacts_fail_test'\n    silo_target = target / 'Silos' / 'cochem_base_silo'\n\n    monkeypatch.setattr('headless_run.provision_silo', lambda *a, **kw: (True, silo_target, True))\n    monkeypatch.setattr('test_suite.run_tests.run_all_preflight_checks', lambda **kw: MockPreflightResultFail())\n    exit_code = headless_run.main([\n        '--artifact-dir', str(target),\n        '--module-dir', str(tmp_path / 'modules'),\n        '--orca-cmd', '/custom/orca',\n        '--mpi-cmd', '/custom/mpirun',\n    ])\n    assert exit_code == 1",
    content
)

path.write_text(content, encoding="utf-8")
print("Done rewriting")
