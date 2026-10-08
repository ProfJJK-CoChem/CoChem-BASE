"""Termination escalation preserves the caller and unrelated sibling jobs."""

import os
import json
from pathlib import Path
import subprocess
import sys
import time

import psutil
import pytest


@pytest.mark.parametrize("module_name", ["cochem.core.process_reaper", "src.cochem.core.process_reaper"])
def test_shared_process_group_escalation_preserves_caller_and_sibling(module_name):
    repo = Path(__file__).resolve().parents[2]
    script = r'''
import importlib
import os
import subprocess
import sys

manager = importlib.import_module(sys.argv[1]).ProcessTreeManager()
unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
target = subprocess.Popen([
    sys.executable, '-u', '-c',
    'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print("ready", flush=True); time.sleep(30)',
], stdout=subprocess.PIPE, text=True)
try:
    assert target.stdout.readline().strip() == 'ready'
    if os.name != 'nt':
        assert os.getpgid(target.pid) == os.getpgrp()
    manager.register_process(target.pid)
    result = manager.terminate_tree(target.pid, grace_timeout_sec=0.1)
    assert result['success']
    assert unrelated.poll() is None
    assert target.poll() is not None
finally:
    for process in (target, unrelated):
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
    target.stdout.close()
'''
    result = subprocess.run(
        [sys.executable, "-c", script, module_name], cwd=repo,
        env=dict(os.environ, PYTHONPATH=os.pathsep.join([str(repo), str(repo / "src")])),
        start_new_session=(os.name != "nt"), capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def _run_owned_python(script, tmp_path, *arguments):
    """Retain bounded, genuine process evidence, including owned forced kills."""
    repo = Path(__file__).resolve().parents[2]
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(repo), str(repo / "src")]),
               COCHEM_ARTIFACT_DIR=str(tmp_path / "artifacts"))
    started = time.monotonic()
    controller = subprocess.Popen(
        [sys.executable, "-u", "-c", script, str(tmp_path), *arguments],
        cwd=repo, env=env, start_new_session=(os.name != "nt"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    forced_kill = None
    try:
        stdout, stderr = controller.communicate(timeout=25)
    except subprocess.TimeoutExpired:
        descendants = psutil.Process(controller.pid).children(recursive=True)
        forced_kill = {"reason": "owned engineering controller deadline",
                       "controller_pid": controller.pid,
                       "recorded_descendants": [child.pid for child in descendants]}
        for child in descendants:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                continue
        controller.kill()
        stdout, stderr = controller.communicate(timeout=5)
        psutil.wait_procs(descendants, timeout=2)
    (tmp_path / "stdout.log").write_text(stdout, encoding="utf-8")
    (tmp_path / "stderr.log").write_text(stderr, encoding="utf-8")
    (tmp_path / "process-evidence.json").write_text(json.dumps({
        "scope": "real owned process and signal engineering; no chemistry acceptance",
        "controller_pid": controller.pid, "return_code": controller.returncode,
        "elapsed_seconds": time.monotonic() - started, "forced_kill": forced_kill,
    }), encoding="utf-8")
    assert forced_kill is None, stderr
    assert controller.returncode == 0, stderr
    return stdout


def test_broker_import_preserves_application_handlers_under_actual_same_thread_lock(tmp_path):
    script = r'''
import os, signal, sys
calls = []
def interrupt(signum, frame):
    calls.append(signum)
def terminate(signum, frame):
    calls.append(signum)
signal.signal(signal.SIGINT, interrupt)
signal.signal(signal.SIGTERM, terminate)
from cochem_base.core_engine import cochem_core_subprocess_broker as broker
from cochem_base import cli
assert signal.getsignal(signal.SIGINT) is interrupt
assert signal.getsignal(signal.SIGTERM) is terminate
with broker._GLOBAL_TRACKING_LOCK:
    os.kill(os.getpid(), signal.SIGINT)
assert calls == [signal.SIGINT]
print("application handlers retained; real same-thread RLock signal delivered")
'''
    _run_owned_python(script, tmp_path)


_OWNED_NATIVE_SIGNAL_SCRIPT = r'''
import json, os, pathlib, signal, subprocess, sys, threading, time
import psutil
from cochem_base.core_engine import cochem_core_subprocess_broker as broker
from cochem_base import cli
workspace = pathlib.Path(sys.argv[1])
transport, event, locking = sys.argv[2:]
pid_path = workspace / "native-pids.json"
release_lock = threading.Event()
lock_ready = threading.Event()
trigger_error = []
sig = signal.SIGTERM if event == "term" else signal.SIGINT
signal.signal(signal.SIGINT, signal.default_int_handler)
signal.signal(signal.SIGTERM, cli.handle_shutdown_signal)
unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
native_script = r"""
import json, os, pathlib, signal, subprocess, sys, time
time.sleep(.05)
child = subprocess.Popen(
    [sys.executable, "-c",
     "import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(30)"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
pathlib.Path(sys.argv[1]).write_text(json.dumps({"launcher":os.getpid(),"grandchild":child.pid}))
if sys.argv[2] == "exit":
    sys.exit(0)
time.sleep(30)
"""
command = [sys.executable, "-u", "-c", native_script, str(pid_path), event]
def hold_tracking_lock():
    with broker._GLOBAL_TRACKING_LOCK:
        lock_ready.set()
        release_lock.wait(15)
def trigger():
    deadline = time.monotonic() + 10
    while not pid_path.exists():
        if time.monotonic() >= deadline:
            trigger_error.append("native process did not publish its actual PIDs")
            return
        time.sleep(.005)
    if locking == "during":
        locker.start()
        if not lock_ready.wait(5):
            trigger_error.append("actual tracking lock was not acquired")
            return
    os.kill(os.getpid(), sig)
locker = threading.Thread(target=hold_tracking_lock, daemon=True)
trigger_thread = None
if event != "exit":
    if locking == "setup":
        locker.start()
        assert lock_ready.wait(5)
    trigger_thread = threading.Thread(target=trigger, daemon=True)
    trigger_thread.start()
owned_broker = None
interrupted = False
started = time.monotonic()
try:
    try:
        if transport == "instance":
            owned_broker = broker.SubprocessBroker(cwd=workspace, total_ram_threshold_gb=10**9)
            result = owned_broker.execute(command, timeout=15, daemonize_on_timeout=False)
            assert event == "exit" and result == 0
        else:
            options = {"start_new_session": False} if transport == "shared" else {}
            result = broker.safe_subprocess_run(
                command, cwd=workspace, required_disk_gb=0,
                capture_output=event != "exit", timeout=15, **options)
            assert event == "exit" and result.returncode == 0
    except KeyboardInterrupt:
        assert event == "int"
        interrupted = True
    except SystemExit as exc:
        assert event == "term" and exc.code == 128 + signal.SIGTERM
        interrupted = True
    assert not trigger_error, trigger_error
    assert interrupted == (event != "exit")
    assert time.monotonic() - started < 10
    actual = json.loads(pid_path.read_text())
    assert not psutil.pid_exists(actual["launcher"]), actual
    assert not psutil.pid_exists(actual["grandchild"]), actual
    assert unrelated.poll() is None
    print(json.dumps({"interrupted":interrupted,"native_pids":actual,
                      "unrelated_pid":unrelated.pid,"unrelated_alive":True}))
finally:
    release_lock.set()
    if locker.is_alive():
        locker.join(2)
    if trigger_thread is not None:
        trigger_thread.join(2)
    if owned_broker is not None:
        owned_broker.close()
    if unrelated.poll() is None:
        unrelated.kill()
    unrelated.wait(timeout=5)
    assert not broker.get_active_popen_processes()
'''


@pytest.mark.parametrize("transport", ["safe", "instance"])
@pytest.mark.parametrize("event", ["int", "term"])
def test_actual_interrupt_reaps_owned_tree_and_preserves_parent_exception_and_sibling(
    tmp_path, transport, event,
):
    _run_owned_python(_OWNED_NATIVE_SIGNAL_SCRIPT, tmp_path, transport, event, "none")


@pytest.mark.parametrize("transport", ["safe", "instance"])
def test_actual_interrupt_during_tracking_registration_cleans_before_unregister(tmp_path, transport):
    _run_owned_python(_OWNED_NATIVE_SIGNAL_SCRIPT, tmp_path, transport, "int", "setup")


def test_actual_shutdown_with_worker_held_tracking_lock_is_bounded_and_reaps_native_tree(tmp_path):
    _run_owned_python(_OWNED_NATIVE_SIGNAL_SCRIPT, tmp_path, "safe", "term", "during")


def test_actual_interrupt_in_shared_group_preserves_controller_and_unrelated_sibling(tmp_path):
    _run_owned_python(_OWNED_NATIVE_SIGNAL_SCRIPT, tmp_path, "shared", "int", "none")


@pytest.mark.parametrize("transport", ["safe", "instance"])
def test_normal_exited_launcher_does_not_leave_owned_grandchild_running(tmp_path, transport):
    _run_owned_python(_OWNED_NATIVE_SIGNAL_SCRIPT, tmp_path, transport, "exit", "none")


def test_public_tracking_preserves_exited_launcher_group_until_real_cleanup(tmp_path):
    script = r'''
import json, pathlib, subprocess, sys, time
import psutil
from cochem_base.core_engine import cochem_core_subprocess_broker as broker
workspace = pathlib.Path(sys.argv[1])
pids = workspace / "pids.json"
unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
launcher = subprocess.Popen([
    sys.executable, "-c",
    "import json,pathlib,subprocess,sys,time; time.sleep(.1); "
    "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
    "pathlib.Path(sys.argv[1]).write_text(json.dumps({'grandchild':child.pid}))",
    str(pids)], start_new_session=True)
broker.register_popen_process(launcher)
second = None
try:
    assert launcher.wait(timeout=5) == 0
    actual = json.loads(pids.read_text())
    assert psutil.pid_exists(actual["grandchild"])
    assert launcher not in broker.get_active_popen_processes()
    # A later registration must not discard the exited launcher's group.
    second = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(7)"])
    broker.register_popen_process(second)
    assert second.wait(timeout=5) == 7
    broker.cleanup_zombie_processes()
    assert not psutil.pid_exists(actual["grandchild"])
    assert unrelated.poll() is None
    assert launcher.wait(timeout=1) == 0
    assert second.wait(timeout=1) == 7
finally:
    broker.cleanup_zombie_processes()
    for proc in (launcher, unrelated, second):
        if proc is not None:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=5)
'''
    _run_owned_python(script, tmp_path)


def test_cli_owned_cleanup_preserves_resource_tracker_and_unrelated_exit_status(tmp_path):
    script = r'''
import os, pathlib, signal, subprocess, sys, time
import psutil
from multiprocessing.resource_tracker import ResourceTracker
from cochem_base.core_engine import cochem_core_subprocess_broker as broker
from cochem_base import cli
tracker = ResourceTracker()
tracker.ensure_running()
unrelated = subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(7)"])
owned = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                         start_new_session=True)
broker.register_popen_process(owned)
try:
    os.kill(tracker._pid, signal.SIGKILL)
    deadline = time.monotonic() + 5
    for pid in (tracker._pid, unrelated.pid):
        while psutil.Process(pid).status() != psutil.STATUS_ZOMBIE:
            assert time.monotonic() < deadline
            time.sleep(.01)
    assert cli.reap_zombie_processes() == 1
    assert owned.wait(timeout=1) == -signal.SIGTERM
    assert unrelated.wait(timeout=1) == 7
    tracker._stop()
    assert tracker._pid is None
finally:
    if tracker._pid is not None:
        tracker._stop()
    for proc in (owned, unrelated):
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
    broker.unregister_popen_process(owned)
print("CLI retained actual unrelated Popen and ResourceTracker wait ownership")
'''
    output = _run_owned_python(script, tmp_path)
    assert "ResourceTracker wait ownership" in output


def test_cleanup_rejects_mismatched_authentic_process_identity_without_signalling(tmp_path):
    script = r'''
import subprocess, sys
import psutil
from cochem_base.core_engine import cochem_core_subprocess_broker as broker
owned = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                         start_new_session=True)
unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                             start_new_session=True)
try:
    actual_other_identity = psutil.Process(unrelated.pid)
    actual_other_identity.create_time()
    assert broker._terminate_owned_popen(
        owned, owns_posix_group=True, leader_identity=actual_other_identity) is False
    assert owned.poll() is None
    assert unrelated.poll() is None
    print("genuine mismatched process identity refused; neither real process signalled")
finally:
    for proc in (owned, unrelated):
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=5)
'''
    _run_owned_python(script, tmp_path)


@pytest.mark.parametrize("arguments", [
    ["mass", "13C"], ["--help"], ["--invalid-cochem-option"],
])
def test_actual_cli_entrypoint_restores_application_handlers_on_return_and_error(tmp_path, arguments):
    script = r'''
import json, signal, sys
from cochem_base import cli
def interrupt(signum, frame):
    raise KeyboardInterrupt
def terminate(signum, frame):
    raise SystemExit(91)
signal.signal(signal.SIGINT, interrupt)
signal.signal(signal.SIGTERM, terminate)
sys.argv = ["cochem"] + json.loads(sys.argv[2])
try:
    code = cli.entrypoint()
    assert code == 0
except SystemExit as exc:
    assert exc.code in (0, 2)
finally:
    assert signal.getsignal(signal.SIGINT) is interrupt
    assert signal.getsignal(signal.SIGTERM) is terminate
print("application handlers restored after genuine CLI execution")
'''
    _run_owned_python(script, tmp_path, json.dumps(arguments))
