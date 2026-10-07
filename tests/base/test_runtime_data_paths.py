"""Runtime configuration and data must remain outside the source tier."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from cochem.core.context import AirGapViolationError, assert_writable_path
from cochem_base.config_loader import get_artifact_dir, resolve_config_path, update_config


def test_artifact_source_and_symlink_destinations_rejected(tmp_path):
    repo = Path(__file__).resolve().parents[2]
    with pytest.raises(AirGapViolationError):
        get_artifact_dir(repo / "artifacts")
    link = tmp_path / "source-alias"
    link.symlink_to(repo, target_is_directory=True)
    with pytest.raises(AirGapViolationError):
        get_artifact_dir(link / "artifacts")


def test_each_source_alias_remains_protected(tmp_path):
    names = ("COCHEM_REPO_DIR", "COCH_SRC", "COCHEM_ROOT")
    environment = {**os.environ, **{name: str(tmp_path / name) for name in names}}
    code = """
import os
from pathlib import Path
from cochem.core.context import AirGapViolationError, assert_writable_path
for name in ('COCHEM_REPO_DIR', 'COCH_SRC', 'COCHEM_ROOT'):
    try:
        assert_writable_path(Path(os.environ[name]) / 'runtime.json')
    except AirGapViolationError:
        continue
    raise AssertionError(name + ' source alias was not protected')
"""
    subprocess.run([sys.executable, "-c", code], env=environment, check=True, timeout=20)


def test_explicit_missing_registry_path_is_preserved(tmp_path):
    requested = tmp_path / "missing.json"
    other = tmp_path / "existing.json"
    other.write_text("{}", encoding="utf-8")
    environment = {**os.environ, "COCHEM_CONFIG": str(other)}
    subprocess.run([sys.executable, "-c",
                    "from pathlib import Path; import sys; "
                    "from cochem_base.config_loader import resolve_config_path; "
                    "assert resolve_config_path(Path(sys.argv[1])) == Path(sys.argv[1])",
                    str(requested)], env=environment, check=True, timeout=20)


def test_atomic_updates_preserve_parallel_keys_and_invalid_input(tmp_path):
    path = tmp_path / "registry.json"
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda i: update_config(str(i), i, path), range(20)))
    assert json.loads(path.read_text()) == {str(i): i for i in range(20)}
    before = path.read_bytes()
    with pytest.raises(ValueError):
        update_config("bad", float("nan"), path)
    assert path.read_bytes() == before


def test_config_update_rejects_source_before_writing():
    path = Path(__file__).resolve().parents[2] / "prohibited-registry.json"
    with pytest.raises(AirGapViolationError):
        update_config("status", "active", path)
    assert not path.exists()


def test_corrupt_configuration_is_not_replaced(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text("{incomplete", encoding="utf-8")
    with pytest.raises(ValueError):
        update_config("status", "active", path)
    assert path.read_text() == "{incomplete"


def test_signed_registry_updates_keep_verified_authority(audited_registry):
    from cochem_base.orchestrator.cochem_system_config import CoChemSystemConfig
    from cochem_base.calc.cochem_calc_execution_router import ExecutionRouter
    config = CoChemSystemConfig.model_validate_json(audited_registry.read_text())
    config.update_checksum()
    audited_registry.write_text(config.model_dump_json(), encoding="utf-8")
    update_config("execution", {"default_engine": "local"}, audited_registry)
    assert ExecutionRouter(audited_registry).registry["execution"]["default_engine"] == "local"
    data = json.loads(audited_registry.read_text())
    data["hardware"]["ram_gb"] += 1
    audited_registry.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid checksum"):
        update_config("execution", {"default_engine": "subprocess"}, audited_registry)
