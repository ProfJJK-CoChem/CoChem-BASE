"""Genuine isolated interpreter, filesystem and process ownership boundaries.

These checks execute real OS processes. No engine, provider response, scientific
observation, controller callback or mandatory ownership gate is replaced.
"""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from scripts.gui_module_controller import (
    MAX_REPORT,
    InstalledControlError,
    InstalledDashboard,
    _cap_diagnostics,
    _launch,
    _report,
    _stop_service,
    run_installed_cli,
)


def test_actual_isolated_child_cannot_import_controller_from_notebook_checkout(tmp_path):
    output = tmp_path / 'logs'
    with pytest.raises(InstalledControlError):
        run_installed_cli('scripts.manage_modules',
            ['verify', '--modules', 'topos', '--root', str(tmp_path / 'missing-modules'), '--json'],
            output, timeout=30)
    assert (output / 'report.json').is_file() and (output / 'diagnostics.log').is_file()
    assert not (tmp_path / 'missing-modules').exists()


def test_real_child_command_is_isolated_and_runs_outside_checkout(tmp_path):
    process, command = _launch('scripts.manage_modules', ['--help'], tmp_path)
    process.wait(timeout=30)
    assert command[:5] == [sys.executable, '-I', '-B', '-m', 'scripts.manage_modules']
    assert (tmp_path / 'report.json').is_file() and (tmp_path / 'diagnostics.log').is_file()


@pytest.mark.parametrize('raw', [b'{"a":1,"a":2}', b'{"a":NaN}', b'null', b'[]'])
def test_control_report_ambiguity_is_rejected_or_remains_explicit_transport_data(tmp_path, raw):
    path = tmp_path / 'report.json'
    path.write_bytes(raw)
    if raw in {b'null', b'[]'}:
        assert _report(path) == json.loads(raw)
    else:
        with pytest.raises(ValueError):
            _report(path)


def test_diagnostics_limit_is_applied_even_after_producer_exit(tmp_path):
    path = tmp_path / 'diagnostics.log'
    with path.open('wb') as stream:
        stream.truncate(MAX_REPORT + 1)
    assert _cap_diagnostics(path)
    assert path.stat().st_size == MAX_REPORT
    assert not _cap_diagnostics(path)


def test_actual_controller_identity_and_repr_preserve_unrelated_process(tmp_path):
    command = [sys.executable, '-I', '-B', '-c', 'import time; time.sleep(60)']
    process = subprocess.Popen(command, start_new_session=True)
    unrelated = subprocess.Popen(command, start_new_session=True)
    actual = psutil.Process(process.pid)
    secret = secrets.token_urlsafe(32)
    dashboard = InstalledDashboard(process, command, actual.create_time(), tmp_path, 'unqualified-interface',
        'http://127.0.0.1:8888/?token=' + secret)
    try:
        assert secret not in repr(dashboard)
        dashboard.command = ['another-program']
        with pytest.raises(RuntimeError, match='ownership'):
            dashboard.stop()
        assert process.poll() is None and unrelated.poll() is None
        dashboard.command = command
        dashboard.stop()
        assert process.poll() is not None and unrelated.poll() is None
        dashboard.stop()
        assert unrelated.poll() is None
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_actual_separate_session_service_is_removed_after_controller_is_gone(tmp_path):
    command = [sys.executable, '-I', '-B', '-c', 'import time; time.sleep(60)']
    service = subprocess.Popen(command, start_new_session=True)
    unrelated = subprocess.Popen(command, start_new_session=True)
    identity = psutil.Process(service.pid)
    proof = {'pid': service.pid, 'create_time': identity.create_time(), 'command': command}
    try:
        with pytest.raises(RuntimeError, match='ownership'):
            _stop_service({**proof, 'create_time': proof['create_time'] + 1})
        assert service.poll() is None and unrelated.poll() is None
        _stop_service(proof)
        assert service.poll() is not None and unrelated.poll() is None
        _stop_service(proof)
    finally:
        if service.poll() is None:
            service.terminate()
        service.wait(timeout=5)
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_source_entrypoint_cannot_claim_installed_base_authority(tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, '-B', str(root / 'scripts/gui_module_controller.py'),
        'status', '--root', str(tmp_path / 'missing-modules')], cwd=root,
        env={**os.environ, 'PYTHONPATH': str(root / 'src') + os.pathsep + str(root)},
        capture_output=True, timeout=30, check=False)
    assert result.returncode != 0
    assert b'actual installed BASE distribution' in result.stderr
    assert not (tmp_path / 'missing-modules').exists()


@pytest.mark.skipif(os.name == 'nt', reason='Supported Linux/WSL session ownership boundary')
def test_slow_controller_cleanup_removes_actual_separate_session_child(tmp_path):
    ready = tmp_path / 'child-pid'
    child_command = [sys.executable, '-I', '-B', '-c', 'import time; time.sleep(60)']
    program = ('import os,signal,subprocess,sys,time; '
               'signal.signal(signal.SIGTERM, signal.SIG_IGN); '
               'child=subprocess.Popen([sys.executable,"-I","-B","-c","import time; time.sleep(60)"],'
               'start_new_session=True); '
               'open(sys.argv[1],"w").write(str(child.pid)); time.sleep(60)')
    command = [sys.executable, '-I', '-B', '-c', program, str(ready)]
    controller = subprocess.Popen(command, start_new_session=True)
    unrelated = subprocess.Popen(child_command, start_new_session=True)
    child = None
    try:
        deadline = time.monotonic() + 5
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        child = psutil.Process(int(ready.read_text()))
        actual = psutil.Process(controller.pid)
        dashboard = InstalledDashboard(controller, command, actual.create_time(), tmp_path,
            'actual-service-ownership-test', 'http://127.0.0.1:8501', service={
                'pid': child.pid, 'create_time': child.create_time(), 'command': child.cmdline()})
        assert child.cmdline() == child_command
        dashboard.stop()
        assert controller.poll() is not None
        assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
        assert unrelated.poll() is None
    finally:
        if controller.poll() is None:
            controller.kill()
        controller.wait(timeout=5)
        if child is not None and child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
            child.kill()
        unrelated.terminate()
        unrelated.wait(timeout=5)
