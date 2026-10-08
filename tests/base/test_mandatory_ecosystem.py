"""Installer trust and transport boundaries; these fixtures perform no chemistry."""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path
from threading import Event, Thread

import pytest

from scripts import manage_modules as manager
from scripts import mandatory_ecosystem as ecosystem


def catalog():
    return manager.load_manifest()["modules"]["topos"]


def kit_sums(folder: Path):
    lines = []
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path != folder / "SHA256SUMS":
            lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + "  " + path.relative_to(folder).as_posix())
    (folder / "SHA256SUMS").write_text("\n".join(lines) + "\n")


@pytest.mark.parametrize("value", ["../escape", "/absolute", "x\\y", "./hidden", "x/../hidden", "file\nnext"])
def test_kit_rejects_noncanonical_member_paths(value):
    with pytest.raises(ValueError):
        ecosystem._relative(value)


@pytest.mark.parametrize("change", ["modified", "unrecorded", "missing", "symlink", "duplicate"])
def test_kit_checksum_inventory_rejects_real_filesystem_changes(tmp_path, change):
    payload = tmp_path / "manifest.json"
    payload.write_text('{}')
    kit_sums(tmp_path)
    assert ecosystem.verify_kit_checksums(tmp_path)["manifest.json"] == ecosystem._hash(payload)
    if change == "modified":
        payload.write_text('{"modified":true}')
    elif change == "unrecorded":
        (tmp_path / "extra.py").write_text('raise RuntimeError("unreviewed")')
    elif change == "missing":
        payload.unlink()
    elif change == "symlink":
        (tmp_path / "redirect").symlink_to(payload)
    else:
        sums = tmp_path / "SHA256SUMS"
        sums.write_text(sums.read_text() * 2)
    with pytest.raises(ValueError):
        ecosystem.verify_kit_checksums(tmp_path)


def test_explicit_complete_kit_is_required_before_fetch_or_environment_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(manager, "fetch_module", lambda *a, **k: pytest.fail("Unexpected source fetch"))
    with pytest.raises(manager.ModuleInstallationError, match="complete reviewed"):
        manager.install_module("topos", catalog(), tmp_path)
    assert not list(tmp_path.iterdir())


def test_new_revision_upgrade_keeps_previous_receipt_when_new_kit_fails(tmp_path):
    previous = {'revision': 'b' * 40, 'status': 'installed', 'adapter': 'topos_geometry'}
    parent = tmp_path / 'topos'
    parent.mkdir()
    receipt = parent / 'installation.json'
    receipt.write_text(json.dumps(previous))
    before = receipt.read_bytes()
    with pytest.raises(ValueError, match='extracted complete kit'):
        ecosystem.install(catalog(), tmp_path, tmp_path / 'absent-kit')
    assert receipt.read_bytes() == before
    assert not (parent / catalog()['revision']).exists()


def test_same_revision_invalid_receipt_does_not_restart_installation(tmp_path):
    parent = tmp_path / 'topos'
    parent.mkdir()
    receipt = parent / 'installation.json'
    receipt.write_text(json.dumps({'revision': catalog()['revision'], 'status': 'installed'}))
    before = receipt.read_bytes()
    with pytest.raises(ValueError, match='receipt differs'):
        ecosystem.install(catalog(), tmp_path, tmp_path / 'absent-kit')
    assert receipt.read_bytes() == before


def test_catalog_rejects_legacy_adapter_and_unreviewed_hashes():
    original = catalog()
    assert ecosystem.validate_spec(original)["schema_version"] == "cochem.mandatory-ecosystem-catalog/2"
    for change in ("adapter", "wheel", "bootstrap"):
        spec = json.loads(json.dumps(original))
        if change == "adapter":
            spec["adapter"] = "topos_geometry"
        elif change == "wheel":
            spec["mandatory_ecosystem"]["topos_wheel_sha256"] = "version-only"
        else:
            del spec["mandatory_ecosystem"]["base_bootstrap_sha256"]["cli.py"]
        with pytest.raises(ValueError):
            ecosystem.validate_spec(spec)


@pytest.mark.parametrize('project', ['base', 'torq'])
def test_companion_source_paths_use_complete_validated_module_specs(tmp_path, project):
    pin = 'a' * 40
    spec = ecosystem._companion_spec(project, pin)
    _, location, source, _ = manager._paths(project, spec, tmp_path)
    assert source == location / 'source'
    assert location == tmp_path / project / pin
    assert spec['operations'] == [] and spec['adapter_requirements'] == []
    assert spec['adapter'] is None


def write_wheel(path: Path, name: str, version: str, members: dict[str, bytes]):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name + '-' + version + '.dist-info/METADATA',
                         f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n')
        for member, data in members.items():
            archive.writestr(member, data)


def test_self_consistent_kit_cannot_replace_catalog_pinned_module_wheels(tmp_path, monkeypatch):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    for name, version in (("cochem_base", "1.0.1"), ("cochem_topos", "0.1.0"), ("cochem_torq", "0.1.0")):
        write_wheel(wheels / (name + '.whl'), name, version, {name + '/test.py': b'infrastructure fixture\n'})
    (tmp_path / "candidate-manifest.json").write_text(json.dumps({
        "schema_version": "cochem-unsigned-download/0.1.0", "engines_included": False,
        "model_weights_included": False, "source_pins": {"BASE": "a" * 40,
        "TORQ": catalog()["mandatory_ecosystem"]["torq_revision"]}}))
    kit_sums(tmp_path)
    monkeypatch.setattr(ecosystem, "verify_current_base_wheel", lambda *a: pytest.fail("Module anchor should reject first"))
    with pytest.raises(ValueError, match="independently reviewed catalog digest"):
        ecosystem.inspect_kit(tmp_path, catalog())


def test_mandatory_wheel_ownership_collision_is_rejected_before_execution(tmp_path, monkeypatch):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    for name, version in (("cochem_base", "1.0.1"), ("cochem_topos", "0.1.0"), ("cochem_torq", "0.1.0")):
        write_wheel(wheels / (name + '.whl'), name, version, {'Libraries/__init__.py': b'ownership fixture\n'})
    (tmp_path / "candidate-manifest.json").write_text(json.dumps({
        "schema_version": "cochem-unsigned-download/0.1.0", "engines_included": False,
        "model_weights_included": False, "source_pins": {"BASE": "a" * 40,
        "TORQ": catalog()["mandatory_ecosystem"]["torq_revision"]}}))
    kit_sums(tmp_path)
    with pytest.raises(ValueError, match="overlapping installed ownership"):
        ecosystem.inspect_kit(tmp_path, catalog())


def test_running_base_same_version_does_not_authorize_other_payload(tmp_path, monkeypatch):
    prefix = tmp_path / "environment"
    prefix.mkdir()
    payload = prefix / "cochem_base/program.py"
    payload.parent.mkdir()
    payload.write_bytes(b'actual installed infrastructure bytes\n')
    metadata_text = 'Metadata-Version: 2.1\nName: cochem_base\nVersion: 1.0.1\n'
    class Distribution:
        version = '1.0.1'
        files = ['cochem_base/program.py']
        def locate_file(self, path):
            return prefix / path
        def read_text(self, name):
            return metadata_text if name == 'METADATA' else None
    monkeypatch.setattr(ecosystem.metadata, 'distribution', lambda name: Distribution())
    monkeypatch.setattr(ecosystem.sys, 'prefix', str(prefix))
    monkeypatch.setattr(ecosystem, '__file__', str(prefix / 'scripts/mandatory_ecosystem.py'))
    wheel = tmp_path / 'base.whl'
    write_wheel(wheel, 'cochem_base', '1.0.1', {'cochem_base/program.py': b'other same-version code\n'})
    with pytest.raises(ValueError, match="currently executing BASE code"):
        ecosystem.verify_current_base_wheel(wheel)


def test_source_archive_hash_alone_cannot_change_pinned_source(tmp_path, monkeypatch):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'program.py').write_bytes(b'original pinned code\n')
    monkeypatch.setattr(manager, '_git', lambda *args: 'program.py')
    archive = tmp_path / 'changed.tar.gz'
    with tarfile.open(archive, 'w:gz') as stream:
        data = b'changed code in self-consistent archive\n'
        info = tarfile.TarInfo('package/program.py')
        info.size = len(data)
        stream.addfile(info, io.BytesIO(data))
    with pytest.raises(ValueError, match="pinned Git"):
        ecosystem.verify_source_archive(archive, source)


def test_new_setup_cannot_select_existing_runtime_or_silo_receipts(monkeypatch):
    monkeypatch.setenv('COCHEM_CONFIG', '/existing/registry.json')
    monkeypatch.setenv('COCHEM_ML_SILO', '/existing/mace')
    monkeypatch.setenv('COCHEM_AIMNET2_SILO', '/existing/aimnet')
    monkeypatch.setenv('COCHEM_MODULES', 'topos')
    monkeypatch.setenv('TOPOS_CONFIG', '/existing/topos.json')
    monkeypatch.setenv('COCHEM_ARTIFACT_DIR', '/existing/runtime')
    monkeypatch.setenv('COCHEM_ARTIFACTS', '/existing/other-runtime')
    monkeypatch.setenv('LD_PRELOAD', '/unreviewed/loader.so')
    monkeypatch.setenv('LD_LIBRARY_PATH', '/unreviewed/libraries')
    monkeypatch.setenv('PYTHONUSERBASE', '/unreviewed/python')
    monkeypatch.setenv('PIP_TARGET', '/existing/packages')
    monkeypatch.setenv('PIP_CONFIG_FILE', '/unreviewed/pip.conf')
    monkeypatch.setenv('PIP_EXTRA_INDEX_URL', 'https://unreviewed.invalid/simple')
    monkeypatch.setenv('COCHEM_ORCA_BIN', '/licensed/job/orca')
    monkeypatch.setenv('PIP_INDEX_URL', 'https://configured.example/simple')
    monkeypatch.setenv('COCHEM_SOURCE_READ_TOKEN', 'infrastructure-test-not-a-real-token')
    environment = ecosystem._setup_environment()
    assert not {'COCHEM_CONFIG', 'COCHEM_ML_SILO', 'COCHEM_AIMNET2_SILO', 'TOPOS_CONFIG', 'COCHEM_SOURCE_READ_TOKEN'} & environment.keys()
    assert environment['COCHEM_MODULES'] == ''
    assert not {'COCHEM_ARTIFACT_DIR', 'COCHEM_ARTIFACTS', 'LD_PRELOAD', 'LD_LIBRARY_PATH',
                'PYTHONUSERBASE', 'PIP_TARGET', 'PIP_EXTRA_INDEX_URL'} & environment.keys()
    assert environment['PIP_CONFIG_FILE'] == os.devnull
    assert environment['COCHEM_ORCA_BIN'] == '/licensed/job/orca'
    assert environment['PIP_INDEX_URL'] == 'https://configured.example/simple'


def test_verification_subprocess_obeys_the_shared_total_deadline(tmp_path):
    """Actual process timeout during verification, before any scientific provider."""
    import psutil

    # Import cost is also inside real receiver budgets; this test specifically
    # exercises termination after the verifier has genuinely started.
    from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run
    assert callable(safe_subprocess_run)
    pidfile = tmp_path / 'verification.pid'
    budget = ecosystem._Budget(1)
    command = [sys.executable, '-I', '-c',
               'import os,pathlib,time; pathlib.Path(__import__("sys").argv[1]).write_text(str(os.getpid())); time.sleep(30)',
               str(pidfile)]
    with pytest.raises(subprocess.TimeoutExpired):
        budget.run(command, env=manager._build_env(), label='real verification timeout')
    assert pidfile.exists(), 'The native verification process must actually start'
    assert not psutil.pid_exists(int(pidfile.read_text())), 'Timed-out verifier must be reaped'
    with pytest.raises(TimeoutError, match='Total module receiver'):
        budget.check()


def test_verification_subprocess_honors_cancellation_and_reaps_child(tmp_path):
    import psutil

    from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessCancelledError
    pidfile = tmp_path / 'verification.pid'
    cancelled = Event()
    def cancel_after_native_launch():
        deadline = time.monotonic() + 5
        while not pidfile.exists() and time.monotonic() < deadline:
            cancelled.wait(0.01)
        cancelled.set()
    waiter = Thread(target=cancel_after_native_launch)
    waiter.start()
    command = [sys.executable, '-I', '-c',
               'import os,pathlib,time; pathlib.Path(__import__("sys").argv[1]).write_text(str(os.getpid())); time.sleep(30)',
               str(pidfile)]
    try:
        with pytest.raises(SubprocessCancelledError):
            ecosystem._Budget(10, cancelled).run(command, env=manager._build_env(), label='real verification cancellation')
    finally:
        waiter.join(timeout=6)
    assert not waiter.is_alive()
    assert pidfile.exists(), 'Cancellation must interrupt a genuinely running verifier'
    assert not psutil.pid_exists(int(pidfile.read_text()))


def test_pre_cancelled_handoff_cannot_invoke_a_provider(tmp_path, monkeypatch):
    from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessCancelledError
    cancelled = Event()
    cancelled.set()
    monkeypatch.setattr(ecosystem, 'verify', lambda *a: pytest.fail('Cancelled before verification/launch'))
    with pytest.raises(SubprocessCancelledError):
        ecosystem.execute(tmp_path / 'absent.json', tmp_path / 'output', catalog(), tmp_path,
                          timeout=30, cancellation_event=cancelled)
    assert not (tmp_path / 'output').exists()


@pytest.mark.parametrize('timeout', [0, -1, float('inf'), float('nan')])
def test_invalid_total_timeout_rejected_before_reading_or_execution(tmp_path, timeout):
    with pytest.raises(ValueError, match='timeout'):
        ecosystem.execute(tmp_path / 'absent.json', tmp_path / 'output', catalog(), tmp_path, timeout=timeout)
    assert not (tmp_path / 'output').exists()


def test_handoff_cli_does_not_convert_failed_provider_status_to_success(monkeypatch, tmp_path, capsys):
    from cochem_base.interfaces import module_execution
    from scripts.run_module_handoff import main
    monkeypatch.setattr(module_execution, 'execute_module_handoff', lambda *a, **k: {'status': 'failed', 'published': False})
    assert main(['--handoff', str(tmp_path / 'input.json'), '--output', str(tmp_path / 'out')]) == 1
    assert json.loads(capsys.readouterr().out)['published'] is False
