"""Installer trust and transport boundaries; these fixtures perform no chemistry."""
from __future__ import annotations

import ast
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import time
import venv
import zipfile
from pathlib import Path
from threading import Event, Thread

import pytest

from scripts import manage_modules as manager
from scripts import mandatory_ecosystem as ecosystem


def catalog():
    """The explicitly selected historical kit never replaces automatic setup."""
    return manager.load_manifest(Path(manager.__file__).with_name("module-distribution-legacy-kit-1.0.1.json"))["modules"]["topos"]


def actual_process(code, *arguments, env=None, cwd=None):
    """Invoke selected source in a real process, without global environment edits."""
    root = Path(ecosystem.__file__).resolve().parents[1]
    loader = "import sys; sys.path[:0] = [sys.argv.pop(1), sys.argv.pop(1)]; "
    return subprocess.run([sys.executable, "-I", "-B", "-c", loader + code,
                           str(root / "src"), str(root), *map(str, arguments)],
                          env=env or manager._build_env(), cwd=cwd, capture_output=True,
                          text=True, timeout=30)


def git(folder, *arguments):
    result = subprocess.run(["git", "-C", str(folder), *arguments],
                            env=manager._build_env(), capture_output=True, text=True,
                            check=True, timeout=30)
    return result.stdout.strip()


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


def test_explicit_expert_install_refuses_absent_kit_before_creating_any_source(tmp_path):
    with pytest.raises(ValueError, match="extracted complete kit"):
        ecosystem.install(catalog(), tmp_path, tmp_path / "absent-kit")
    assert not list(tmp_path.iterdir())


def test_new_revision_upgrade_keeps_previous_receipt_when_new_kit_fails(tmp_path):
    previous = manager.load_manifest()["modules"]["topos"]
    assert previous["revision"] != catalog()["revision"]
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
    pin = git(Path(__file__).resolve().parents[2], "rev-parse", "HEAD")
    spec = ecosystem._companion_spec(project, pin)
    _, location, source, _ = manager._paths(project, spec, tmp_path)
    assert source == location / 'source'
    policy_sha = hashlib.sha256(
        json.dumps(spec, sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()
    assert location == tmp_path / project / pin / 'policies' / policy_sha
    assert spec['operations'] == [] and spec['adapter_requirements'] == []
    assert spec['adapter'] is None


def write_wheel(path: Path, name: str, version: str, members: dict[str, bytes]):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(name + '-' + version + '.dist-info/METADATA',
                         f'Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n')
        for member, data in members.items():
            archive.writestr(member, data)


def test_self_consistent_kit_cannot_replace_catalog_pinned_module_wheels(tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    for project, package in ecosystem.PACKAGES.items():
        name = package.replace('-', '_').lower()
        write_wheel(wheels / (name + '.whl'), name, ecosystem.VERSIONS[project],
                    {name + '/test.py': b'explicitly unreviewed installer input\n'})
    (tmp_path / "candidate-manifest.json").write_text(json.dumps({
        "schema_version": "cochem-unsigned-download/0.1.0", "engines_included": False,
        "model_weights_included": False, "source_pins": {"BASE": git(Path(__file__).resolve().parents[2], "rev-parse", "HEAD"),
        "TORQ": catalog()["mandatory_ecosystem"]["torq_revision"]}}))
    kit_sums(tmp_path)
    with pytest.raises(ValueError, match="independently reviewed catalog digest"):
        ecosystem.inspect_kit(tmp_path, catalog())


def test_mandatory_wheel_ownership_collision_is_rejected_before_execution(tmp_path):
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    for project, package in ecosystem.PACKAGES.items():
        name = package.replace('-', '_').lower()
        write_wheel(wheels / (name + '.whl'), name, ecosystem.VERSIONS[project],
                    {'Libraries/__init__.py': b'explicitly conflicting ownership input\n'})
    (tmp_path / "candidate-manifest.json").write_text(json.dumps({
        "schema_version": "cochem-unsigned-download/0.1.0", "engines_included": False,
        "model_weights_included": False, "source_pins": {"BASE": git(Path(__file__).resolve().parents[2], "rev-parse", "HEAD"),
        "TORQ": catalog()["mandatory_ecosystem"]["torq_revision"]}}))
    kit_sums(tmp_path)
    with pytest.raises(ValueError, match="overlapping installed ownership"):
        ecosystem.inspect_kit(tmp_path, catalog())


def test_running_installed_verifier_rejects_changed_same_version_wheel_bytes(tmp_path):
    """Build the complete historical BASE wheel; verify provenance, not chemistry."""
    source = tmp_path / 'source'
    source.mkdir()
    revision = '43fdc580ca2ee668d34a6c267cf1f7d4b18df762'
    repository = Path(__file__).resolve().parents[2]
    present = subprocess.run(['git', '-C', str(repository), 'cat-file', '-e', revision + '^{commit}'],
                             env=manager._build_env(), capture_output=True, timeout=30)
    if present.returncode:
        # Fresh shallow checkouts obtain actual immutable public history, without
        # changing the student's checkout or substituting another package.
        repository = tmp_path / 'historical-git'
        repository.mkdir()
        git(repository, 'init')
        git(repository, 'fetch', '--depth=1', '--no-tags',
            'https://github.com/ProfJJK-CoChem/CoChem-BASE.git', revision)
    archive = tmp_path / 'historical-base.tar'
    git(repository, 'archive', '--format=tar', '-o', str(archive), revision)
    with tarfile.open(archive) as historical:
        historical.extractall(source, filter='data')
    current_code = Path(ecosystem.__file__).read_text()
    archived_code = (source / 'scripts/mandatory_ecosystem.py').read_text()
    current_verifier, = [node for node in ast.parse(current_code).body
                        if isinstance(node, ast.FunctionDef) and node.name == 'verify_current_base_wheel']
    archived_verifier, = [node for node in ast.parse(archived_code).body
                         if isinstance(node, ast.FunctionDef) and node.name == 'verify_current_base_wheel']
    assert ast.get_source_segment(current_code, current_verifier) == ast.get_source_segment(archived_code, archived_verifier), \
        'The actually installed historical verifier must be the current verifier under test'
    wheels = tmp_path / 'wheels'
    wheels.mkdir()
    built = subprocess.run([sys.executable, '-I', '-B', '-c',
        'import os,sys; os.chdir(sys.argv[1]); from setuptools import build_meta; print(build_meta.build_wheel(sys.argv[2]))',
        str(source), str(wheels)], env=manager._build_env(), capture_output=True, text=True, timeout=60)
    assert built.returncode == 0, built.stderr
    wheel, = wheels.glob('*.whl')
    prefix = tmp_path / "environment"
    venv.EnvBuilder(with_pip=False).create(prefix)
    python = manager._python_path(prefix)
    installed = subprocess.run([sys.executable, '-I', '-m', 'pip', '--python', str(python),
        'install', '--no-index', '--no-deps', '--no-compile', str(wheel)],
        env=manager._build_env(), capture_output=True, text=True, timeout=60)
    assert installed.returncode == 0, installed.stderr
    command = [str(python), '-I', '-B', '-c',
               'from pathlib import Path; import sys; from scripts.mandatory_ecosystem import verify_current_base_wheel; verify_current_base_wheel(Path(sys.argv[1]))']
    accepted = subprocess.run(command + [str(wheel)], env=manager._build_env(), cwd=tmp_path,
                              capture_output=True, text=True, timeout=30)
    assert accepted.returncode == 0, accepted.stderr
    altered = tmp_path / 'changed-same-version.whl'
    with zipfile.ZipFile(wheel) as original, zipfile.ZipFile(altered, 'w') as changed:
        for member in original.infolist():
            data = original.read(member)
            if member.filename == 'scripts/__init__.py':
                data += b'\n# deliberately changed installer-control bytes\n'
            changed.writestr(member, data)
    rejected = subprocess.run(command + [str(altered)], env=manager._build_env(), cwd=tmp_path,
                              capture_output=True, text=True, timeout=30)
    assert rejected.returncode != 0
    assert 'currently executing BASE code' in rejected.stderr


def test_source_archive_hash_alone_cannot_change_pinned_source(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'program.py').write_bytes(Path(ecosystem.__file__).read_bytes())
    git(source, 'init')
    git(source, 'add', '.')
    git(source, '-c', 'user.name=CoChem installer boundary', '-c', 'user.email=boundary@example.invalid',
        'commit', '-m', 'Actual verifier source for archive integrity control')
    original = tmp_path / 'original.tar.gz'
    git(source, 'archive', '--format=tar.gz', '--prefix=package/', '-o', str(original), 'HEAD')
    ecosystem.verify_source_archive(original, source)
    archive = tmp_path / 'changed.tar.gz'
    with tarfile.open(archive, 'w:gz') as stream:
        data = b'changed code in self-consistent archive\n'
        info = tarfile.TarInfo('package/program.py')
        info.size = len(data)
        stream.addfile(info, io.BytesIO(data))
    with pytest.raises(ValueError, match="pinned Git"):
        ecosystem.verify_source_archive(archive, source)


def test_new_setup_cannot_select_existing_runtime_or_silo_receipts(tmp_path):
    inputs = {
        'COCHEM_CONFIG': str(tmp_path / 'registry.json'), 'COCHEM_ML_SILO': str(tmp_path / 'mace'),
        'COCHEM_AIMNET2_SILO': str(tmp_path / 'aimnet'), 'COCHEM_MODULES': 'topos',
        'TOPOS_CONFIG': str(tmp_path / 'topos.json'), 'COCHEM_ARTIFACT_DIR': str(tmp_path / 'runtime'),
        'COCHEM_ARTIFACTS': str(tmp_path / 'other-runtime'), 'LD_PRELOAD': str(tmp_path / 'absent-loader.so'),
        'LD_LIBRARY_PATH': str(tmp_path / 'libraries'), 'PYTHONUSERBASE': str(tmp_path / 'python'),
        'PIP_TARGET': str(tmp_path / 'packages'), 'PIP_CONFIG_FILE': str(tmp_path / 'pip.conf'),
        'PIP_EXTRA_INDEX_URL': 'https://unreviewed.invalid/simple', 'COCHEM_ORCA_BIN': '/licensed/job/orca',
        'PIP_INDEX_URL': 'https://configured.example/simple',
        'COCHEM_SOURCE_CREDENTIAL': 'explicit-invalid-credential-control'}
    contaminated = manager._build_env()
    contaminated.update(inputs)
    checked = actual_process('import json; from scripts.mandatory_ecosystem import _setup_environment; print(json.dumps(_setup_environment()))',
                             env=contaminated, cwd=tmp_path)
    assert checked.returncode == 0, checked.stderr
    assert inputs['COCHEM_SOURCE_CREDENTIAL'] not in checked.stdout
    environment = json.loads(checked.stdout)
    assert not {'COCHEM_CONFIG', 'COCHEM_ML_SILO', 'COCHEM_AIMNET2_SILO', 'TOPOS_CONFIG', 'COCHEM_SOURCE_CREDENTIAL'} & environment.keys()
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


def test_pre_cancelled_handoff_cannot_read_even_an_absent_input(tmp_path):
    from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessCancelledError
    cancelled = Event()
    cancelled.set()
    with pytest.raises(SubprocessCancelledError):
        ecosystem.execute(tmp_path / 'absent.json', tmp_path / 'output', catalog(), tmp_path,
                          timeout=30, cancellation_event=cancelled)
    assert not (tmp_path / 'output').exists()


@pytest.mark.parametrize('timeout', [0, -1, float('inf'), float('nan')])
def test_invalid_total_timeout_rejected_before_reading_or_execution(tmp_path, timeout):
    with pytest.raises(ValueError, match='timeout'):
        ecosystem.execute(tmp_path / 'absent.json', tmp_path / 'output', catalog(), tmp_path, timeout=timeout)
    assert not (tmp_path / 'output').exists()


def test_handoff_cli_refuses_absent_installation_without_publishing_science(tmp_path):
    from cochem_base.interfaces.artifact_handoff import prepare_module_handoff
    source = Path(__file__).resolve().parents[1] / 'data/orca_6_1_1_water_hf_sto3g/water.xyz'
    package = tmp_path / 'handoff'
    prepare_module_handoff('topos', source, package, operation='geometry_analysis')
    before = {path.name: path.read_bytes() for path in package.iterdir() if path.is_file()}
    output = tmp_path / 'out'
    result = actual_process('from scripts.run_module_handoff import main; raise SystemExit(main(__import__("sys").argv[1:]))',
                           '--handoff', package / 'handoff.json', '--output', output,
                           '--root', tmp_path / 'absent-installation', cwd=tmp_path)
    assert result.returncode != 0
    assert 'Cannot read a valid module receipt at ' in result.stderr
    assert str(tmp_path / 'absent-installation/topos/installation.json') in result.stderr
    assert '"status": "completed"' not in result.stdout
    assert '"published": true' not in result.stdout
    assert not output.exists()
    assert {path.name: path.read_bytes() for path in package.iterdir() if path.is_file()} == before
