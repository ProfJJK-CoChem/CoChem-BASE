"""Real isolated CLI forwarding/execution; no workflow/installer success doubles."""
from pathlib import Path
import json
import os
import signal
import time
import subprocess

import psutil
import pytest

from scripts import manage_modules as installer
from tests.base.test_pinned_pip_runtime import (
    _caller_pip,
    _inspect,
    _project,
    _tree,
    bare_python,  # noqa: F401 - imported real pytest fixture
    offline_env,  # noqa: F401 - imported real pytest fixture
    wheel,  # noqa: F401 - imported real pytest fixture
)


SCRIPT = Path(installer.__file__).resolve()


def _cli_command(python, arguments, env, *, timeout='45'):
    scripts = [str(SCRIPT)]
    if env.get('COCHEM_SOURCE_QUARANTINE_ROOT'):
        source = Path(env['COCHEM_SOURCE_QUARANTINE_ROOT'])
        assert source.resolve() == SCRIPT.parents[1]
        scripts.insert(0, str(source/'ci_tools/source_quarantine.py'))
    return [str(python), '-I', '-B', *scripts, 'pip', '--timeout', timeout, '--', *arguments]


def _cli(python, arguments, env, *, timeout='45'):
    return subprocess.run(_cli_command(python, arguments, env, timeout=timeout),
                          env=env, capture_output=True, text=True, timeout=60, check=False)


def test_cli_real_offline_build_install_uninstall_and_target_prefix(
        wheel, bare_python, offline_env, tmp_path, pinned_pip_test_artifact):
    assert wheel == pinned_pip_test_artifact
    python, target = bare_python
    before = _caller_pip()
    env = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(wheel))
    project, wheels = tmp_path/'project with spaces', tmp_path/'built wheels'
    marker = _project(project)
    built = _cli(python, ['wheel', '--no-deps', '--no-index', '--wheel-dir', str(wheels), str(project)], env)
    assert built.returncode == 0, built.stdout + built.stderr
    assert marker.read_text() == 'real PEP 517 build'
    artifacts = list(wheels.glob('*.whl'))
    assert len(artifacts) == 1
    installed = _cli(python, ['install', '--no-deps', '--no-index', str(artifacts[0])], env)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    observed = _inspect(python, offline_env)
    assert Path(observed['prefix']).resolve() == target.resolve()
    assert observed['fixture_value'] == 42
    assert Path(observed['fixture_origin']).resolve().is_relative_to(target.resolve())
    assert observed['distributions']['cochem-installer-fixture']['version'] == '1.2.3'
    assert observed['distributions']['cochem-installer-fixture']['direct_url']['url'] == artifacts[0].as_uri()
    assert 'pip' not in observed['distributions']  # Target and caller installed pip were not upgraded.
    removed = _cli(python, ['uninstall', '--yes', 'cochem-installer-fixture'], env)
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert _inspect(python, offline_env)['distributions'] == {}
    assert _caller_pip() == before


def test_cli_preserves_real_version_stdout_and_nonzero_stderr(wheel, bare_python, offline_env):
    python, target = bare_python
    before, caller = _tree(target), _caller_pip()
    env = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(wheel))
    version = _cli(python, ['--version'], env)
    assert version.returncode == 0 and version.stdout.startswith('pip 26.2 '), version.stderr
    arguments = ['--cochem-real-invalid-option-for-cli-control']
    with installer._pip_command(python, arguments, env=env, timeout=45) as (command, prepared, remaining):
        direct = subprocess.run(command, env=prepared, timeout=remaining,
                                capture_output=True, text=True, check=False)
    actual = _cli(python, arguments, env)
    assert direct.returncode != 0 and actual.returncode == direct.returncode
    assert 'no such option' in direct.stderr and 'no such option' in actual.stderr
    assert 'Module pip failed' not in actual.stderr
    assert _tree(target) == before and _caller_pip() == caller


@pytest.mark.parametrize('kind', ['missing', 'corrupt'])
def test_cli_artifact_refuses_before_backend_or_target_mutation(
        kind, wheel, bare_python, offline_env, tmp_path):
    python, target = bare_python
    before, caller = _tree(target), _caller_pip()
    bad = tmp_path/'unavailable-or-corrupt-pip.whl'
    if kind == 'corrupt':
        data = bytearray(wheel.read_bytes())
        data[0] ^= 1
        bad.write_bytes(data)
    env = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(bad))
    project = tmp_path/'unexecuted project'
    marker = _project(project)
    output = tmp_path/'uncreated wheels'
    actual = _cli(python, ['wheel', '--no-deps', '--no-index', '--wheel-dir', str(output), str(project)], env)
    assert actual.returncode == 1
    assert ('missing, redirected or has the wrong size' if kind == 'missing' else
            'checksum verification failed') in actual.stderr
    assert not marker.exists() and not output.exists()
    assert _tree(target) == before and _caller_pip() == caller


@pytest.mark.parametrize('timeout', ['0', 'nan', 'inf'])
def test_cli_rejects_nonpositive_or_nonfinite_budget_without_tool(
        timeout, bare_python, offline_env, tmp_path):
    python, target = bare_python
    before = _tree(target)
    env = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(tmp_path/'missing.whl'))
    actual = _cli(python, ['--version'], env, timeout=timeout)
    assert actual.returncode == 1
    assert 'finite positive setup budget' in actual.stderr
    assert _tree(target) == before


def test_cli_requires_a_forwarded_command_before_artifact_access(bare_python, offline_env, tmp_path):
    python, target = bare_python
    before = _tree(target)
    env = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(tmp_path/'missing.whl'))
    actual = _cli(python, [], env)
    assert actual.returncode == 2 and 'requires a command after --' in actual.stderr
    assert _tree(target) == before


@pytest.mark.parametrize('stop_kind', ['timeout', 'interrupt'])
def test_cli_stops_real_pep517_backend_descendant(stop_kind, wheel, bare_python, offline_env, tmp_path):
    python, target = bare_python
    before, caller = _tree(target), _caller_pip()
    env = dict(offline_env, COCHEM_PINNED_PIP_WHEEL=str(wheel))
    project = tmp_path/'timed backend'
    _project(project)
    backend = project/'backend.py'
    child_marker = project/'actual-backend-child.json'
    child_code = ("import json,os,pathlib,sys,time; target=pathlib.Path(sys.argv[1]); "
                  "pending=target.with_suffix('.tmp'); "
                  "pending.write_text(json.dumps({'pid':os.getpid(),'ppid':os.getppid()})); "
                  "pending.replace(target); time.sleep(60)")
    body = backend.read_text()
    anchor = "    pathlib.Path(__file__).with_name('backend-executed').write_text('real PEP 517 build')\n"
    pause = ("    import subprocess, sys, time\n"
             f"    child = subprocess.Popen([sys.executable, '-I', '-B', '-c', {child_code!r}, {str(child_marker)!r}], stdin=subprocess.DEVNULL)\n"
             "    time.sleep(60)\n")
    assert body.count(anchor) == 1
    backend.write_text(body.replace(anchor, anchor+pause, 1))
    command = _cli_command(python, ['wheel', '--no-index', '--no-deps', '--wheel-dir',
        str(tmp_path/'timed wheels'), str(project)], env, timeout='8' if stop_kind == 'timeout' else '45')
    started = time.monotonic()
    options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {}
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, **options)
    witness = None
    try:
        deadline = started+12
        while not child_marker.exists() and process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert child_marker.exists(), 'Actual PEP517 backend child did not start before the bounded timeout'
        actual = json.loads(child_marker.read_text())
        child = psutil.Process(actual['pid'])
        witness = {'pid': child.pid, 'create_time': child.create_time(), 'parent_pid': child.ppid(),
                   'CLI_pid': process.pid, 'CLI_create_time': psutil.Process(process.pid).create_time()}
        assert child.is_running() and child.status() != psutil.STATUS_ZOMBIE
        assert witness['parent_pid'] == actual['ppid']
        assert child.pid in {member.pid for member in psutil.Process(process.pid).children(recursive=True)}
        if stop_kind == 'interrupt':
            process.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGTERM)
        stdout, stderr = process.communicate(timeout=20)
        elapsed = time.monotonic()-started
        if stop_kind == 'timeout':
            assert process.returncode == 124, stdout+stderr
            assert 'exceeded its' in stderr and 8 <= elapsed < 25
        else:
            assert process.returncode not in (0, 124), stdout+stderr
            assert 'interrupted by signal' in stderr and 'after confirmed owned cleanup' in stderr
            assert 0 < elapsed < 25
        assert 'UNCONFIRMED' not in stderr
        try:
            remaining = psutil.Process(witness['pid'])
            old_generation_still_present = remaining.create_time() == witness['create_time']
        except psutil.NoSuchProcess:
            old_generation_still_present = False
        assert not old_generation_still_present, 'Owned backend child generation remained after CLI timeout'
        (tmp_path/'TIMEOUT_WITNESS.json').write_text(json.dumps({**witness,
            'CLI_exit_code': process.returncode, 'stop_kind': stop_kind, 'elapsed_seconds': elapsed,
            'original_child_generation_absent': True})+'\n')
        assert _tree(target) == before and _caller_pip() == caller
    finally:
        # Failure cleanup is identity-scoped and never precedes the acceptance
        # assertions above; it cannot manufacture a passing owner observation.
        if process.poll() is None:
            process.terminate()
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate(timeout=5)
        if witness is not None:
            try:
                child = psutil.Process(witness['pid'])
                if child.create_time() == witness['create_time']:
                    child.kill()
                    child.wait(timeout=5)
            except psutil.NoSuchProcess:
                pass
