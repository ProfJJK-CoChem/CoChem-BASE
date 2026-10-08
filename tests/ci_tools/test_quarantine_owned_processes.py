"""Genuine subprocess controls for quarantine lifetime ownership.

These controls exercise native POSIX groups or Windows Jobs. They distinguish
process termination from OS-owned collection of a terminal process identity.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import psutil
import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
RUNNER = REPOSITORY / "ci_tools" / "zero_trust_runner.py"


CONTROL_SUPPORT = r'''
import ctypes, json, os, psutil, signal, subprocess, time
from ctypes import wintypes

def assert_stopped(pid, timeout=2):
    deadline = time.monotonic() + timeout
    observed = []
    while True:
        try:
            status = psutil.Process(pid).status()
        except psutil.NoSuchProcess:
            return {'pid':pid, 'state':'collected'}
        observed.append(status)
        if os.name == 'nt':
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            kernel.GetExitCodeProcess.restype = wintypes.BOOL
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.restype = wintypes.BOOL
            handle = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)
            if handle:
                try:
                    code = wintypes.DWORD()
                    assert kernel.GetExitCodeProcess(handle, ctypes.byref(code))
                    if kernel.WaitForSingleObject(handle, 0) == 0 and code.value != 259:
                        return {'pid':pid, 'state':'kernel-signaled-exited', 'exit_code':code.value}
                finally:
                    assert kernel.CloseHandle(handle)
            elif ctypes.get_last_error() not in (87,):
                raise ctypes.WinError(ctypes.get_last_error())
        elif status == psutil.STATUS_ZOMBIE and not sys.platform.startswith('linux'):
            # It cannot execute; the host's reaper, rather than this caller,
            # owns collection of a non-child's terminal identity.
            return {'pid':pid, 'state':'terminal-zombie-awaiting-system-reaper'}
        if time.monotonic() >= deadline:
            raise AssertionError(json.dumps({'still_not_terminated':pid, 'statuses':observed}))
        time.sleep(0.01)

def assert_private(quarantine):
    if os.name == 'posix':
        import stat
        mode = stat.S_IMODE(quarantine.quarantine_dir.stat().st_mode)
        assert mode == 0o700, mode
        return {'model':'posix-mode', 'mode':'0700'}
    from ci_tools.zero_trust_runner import _windows_directory_security
    result = _windows_directory_security(quarantine.quarantine_dir, enforce=False)
    assert result['protected_dacl']
    return {'model':'windows-protected-dacl', **result}

def launcher_script(exit_code=None, inherit_pipes=True):
    ready = evidence_dir / 'worker-ready.txt'
    worker = (
        "import os,signal,sys,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN) if os.name=='posix' else None; "
        "Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
    )
    options = '' if inherit_pipes else ',stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL'
    return '\n'.join([
        'import json,os,subprocess,sys,time; from pathlib import Path',
        'child=subprocess.Popen([sys.executable,"-B","-c",' + repr(worker) + ',' + repr(str(ready)) + ']' + options + ')',
        'deadline=time.monotonic()+5',
        'while not Path(' + repr(str(ready)) + ').exists():',
        '    if time.monotonic()>deadline: raise RuntimeError("worker readiness deadline")',
        '    time.sleep(0.01)',
        'Path(' + repr(str(evidence_dir/'owned.json')) + ').write_text(json.dumps({"launcher_pid":os.getpid(),"worker_pid":child.pid}))',
        'time.sleep(30)' if exit_code is None else 'raise SystemExit(' + repr(exit_code) + ')',
    ])
'''


def _publish_control_receipt(receipt: dict) -> None:
    supplied = os.environ.get("COCHEM_CI_CONTROL_EVIDENCE_DIR")
    if not supplied:
        return
    destination = Path(supplied)
    if (not destination.is_absolute() or destination.is_symlink() or not destination.is_dir()
            or destination.resolve() != destination.absolute()
            or destination.resolve().is_relative_to(REPOSITORY)):
        raise ValueError("Process-control evidence requires an external existing regular directory")
    payload = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode("utf-8")
    target = destination / ("process-control-" + hashlib.sha256(payload).hexdigest() + ".json")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(target, flags, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(payload)


def _run_control(tmp_path: Path, body: str) -> dict:
    before = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
    control = tmp_path / "control.py"
    control.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(REPOSITORY)!r})\n"
        "from pathlib import Path\n"
        f"evidence_dir = Path({str(tmp_path)!r})\n"
        + textwrap.dedent(CONTROL_SUPPORT)
        + textwrap.dedent(body), encoding="utf-8",
    )
    start = time.monotonic()
    job = None
    options = {"start_new_session": os.name != "nt"}
    if os.name == "nt":
        from ci_tools.zero_trust_runner import _WindowsJob
        job = _WindowsJob()
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004
    try:
        process = subprocess.Popen(
            [sys.executable, "-B", str(control)], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, **options,
        )
    except BaseException:
        if job is not None:
            job.close()
        raise
    forced_cleanup = False
    try:
        if job is not None:
            job.assign_and_resume(process)
        stdout, stderr = process.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        forced_cleanup = True
        if job is not None:
            assert job.stop(3)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=3)
    except BaseException:
        if job is not None:
            assert job.stop(3)
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                process.poll()
        if process.poll() is None:
            process.kill()
        process.wait(timeout=3)
        raise
    finally:
        # Any failed control's explicit owned group is removed by its controller,
        # without turning forced cleanup into a passing lifetime observation.
        owned_path = tmp_path / "owned.json"
        if job is not None:
            deadline = time.monotonic() + 1
            while job.active_processes() and time.monotonic() < deadline:
                time.sleep(0.01)
            forced_cleanup = forced_cleanup or bool(job.active_processes())
            assert job.stop(3)
        elif owned_path.exists():
            group_id = json.loads(owned_path.read_text())["launcher_pid"]
            try:
                os.killpg(group_id, 0)
            except ProcessLookupError:
                group_id = None
            live_members = []
            if group_id is not None:
                for member in psutil.process_iter(["pid"]):
                    try:
                        if member.pid <= 0 or os.getpgid(member.pid) != group_id:
                            continue
                        current = psutil.Process(member.pid)
                        current.create_time()
                        status = current.status()
                        if not current.is_running():
                            if psutil.pid_exists(current.pid):
                                live_members.append(current.pid)
                            continue
                        if os.getpgid(current.pid) != group_id:
                            live_members.append(current.pid)
                        elif sys.platform.startswith("linux") or status != psutil.STATUS_ZOMBIE:
                            live_members.append(current.pid)
                    except (ProcessLookupError, psutil.NoSuchProcess):
                        continue
            if live_members:
                forced_cleanup = True
                os.killpg(group_id, signal.SIGKILL)
    after = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
    receipt = {
        "platform": sys.platform, "python": sys.executable,
        "returncode": process.returncode, "stdout": stdout, "stderr": stderr,
        "duration_s": time.monotonic() - start, "forced_cleanup": forced_cleanup,
        "runner_sha256_before": before, "runner_sha256_after": after,
    }
    (tmp_path / "control-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8",
    )
    if forced_cleanup or process.returncode != 0 or before != after:
        _publish_control_receipt(receipt)
    assert before == after
    assert not forced_cleanup, json.dumps(receipt, indent=2)
    assert process.returncode == 0, json.dumps(receipt, indent=2)
    observations = json.loads(stdout.strip().splitlines()[-1])
    receipt["observations"] = observations
    (tmp_path / "control-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8",
    )
    _publish_control_receipt(receipt)
    return observations


@pytest.mark.parametrize("exit_code", [0, 7])
@pytest.mark.parametrize("inherit_pipes", [False, True])
def test_exited_launcher_cleans_workers_and_preserves_unrelated_owners(
    tmp_path: Path, exit_code: int, inherit_pipes: bool,
) -> None:
    observations = _run_control(tmp_path, f'''
        import json, os, shutil, stat, subprocess, time
        import psutil
        from multiprocessing import resource_tracker, shared_memory
        from ci_tools.zero_trust_runner import QuarantineEnvironment

        tracker_memory = shared_memory.SharedMemory(create=True, size=16)
        tracker_pid = resource_tracker._resource_tracker._pid if os.name == 'posix' else None
        tracker_memory.buf[:4] = b"live"
        unrelated = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"])
        owned_status = subprocess.Popen([sys.executable, "-B", "-c", "raise SystemExit(7)"])
        original_umask = os.umask(0) if os.name == 'posix' else None
        launch_code = launcher_script({exit_code}, {inherit_pipes!r})
        try:
            start = time.monotonic()
            with QuarantineEnvironment() as quarantine:
                privacy_before = assert_private(quarantine)
                copied_source = evidence_dir / "copied-source"
                copied_source.mkdir(mode=0o755)
                shutil.copytree(copied_source, quarantine.quarantine_dir, dirs_exist_ok=True)
                if os.name == 'posix':
                    assert stat.S_IMODE(quarantine.quarantine_dir.stat().st_mode) == 0o755
                result = quarantine.run_command([sys.executable, "-B", "-c", launch_code], timeout=1)
                privacy_after = assert_private(quarantine)
            owned = json.loads((evidence_dir / "owned.json").read_text())
            worker_termination = assert_stopped(owned["worker_pid"])
            cleanup = result.cleanup_observation
            assert cleanup is not None and cleanup.owned_work_stopped
            assert cleanup.launcher_pid == owned['launcher_pid']
            assert cleanup.launcher_returncode is not None
            assert result.to_dict()['cleanup_observation'] == cleanup.to_dict()
            if sys.platform.startswith('linux'):
                assert not cleanup.external_reaping_pending
            assert unrelated.poll() is None
            assert owned_status.wait(timeout=3) == 7
            if tracker_pid is not None:
                assert psutil.Process(tracker_pid).status() != psutil.STATUS_ZOMBIE
            assert bytes(tracker_memory.buf[:4]) == b"live"
            mirror = shared_memory.SharedMemory(name=tracker_memory.name)
            assert bytes(mirror.buf[:4]) == b"live"
            mirror.close()
            if {inherit_pipes!r}:
                assert result.exit_code == 124 and result.timed_out and not result.passed
            else:
                assert result.exit_code == {exit_code} and not result.timed_out
                assert result.passed is ({exit_code} == 0)
            assert time.monotonic() - start < 8
            print(json.dumps({{"result": result.to_dict(), "owned": owned,
                              "unrelated_survived": True, "shared_memory_survived": True,
                              "tracker_pid": tracker_pid, "worker_termination": worker_termination,
                              "privacy_before": privacy_before, "privacy_after": privacy_after,
                              "controller_umask": "0000" if original_umask is not None else None,
                              "copied_root_mode_repaired": True,
                              "other_popen_status": 7}}))
        finally:
            if original_umask is not None:
                os.umask(original_umask)
            unrelated.kill()
            unrelated.wait(timeout=3)
            if owned_status.poll() is None:
                owned_status.kill()
                owned_status.wait(timeout=3)
            tracker_memory.close()
            tracker_memory.unlink()
    ''')
    assert observations["unrelated_survived"] and observations["shared_memory_survived"]


@pytest.mark.parametrize("exception_name", ["KeyboardInterrupt", "SystemExit"])
def test_interruption_preserves_original_exception_and_stops_owned_tree(
    tmp_path: Path, exception_name: str,
) -> None:
    observations = _run_control(tmp_path, f'''
        import json, os, signal, subprocess, threading, time
        import psutil
        from ci_tools.zero_trust_runner import QuarantineEnvironment
        launch_code = launcher_script()
        command = [sys.executable, "-B", "-c", launch_code]
        def interrupt(signum, frame):
            raise {exception_name}(17)
        def cancel_at_communicate(frame, event, arg):
            if (event == "call" and frame.f_code is subprocess.Popen.communicate.__code__
                    and frame.f_locals['self'].args == command):
                deadline = time.monotonic() + 5
                while True:
                    try:
                        actual = json.loads((evidence_dir / "owned.json").read_text())
                        assert psutil.Process(actual['worker_pid']).status() != psutil.STATUS_ZOMBIE
                        break
                    except (FileNotFoundError, json.JSONDecodeError):
                        if time.monotonic() > deadline:
                            raise AssertionError("real worker readiness deadline")
                        time.sleep(0.01)
                sys.settrace(None)
                raise {exception_name}(17)
            return None
        original = signal.signal(signal.SIGALRM, interrupt) if os.name == 'posix' else None
        notification_done = threading.Event()
        notifier = None
        notification_errors = []
        def notify_on_ready():
            deadline = time.monotonic() + 5
            while not notification_done.is_set():
                try:
                    actual = json.loads((evidence_dir/'owned.json').read_text())
                    assert psutil.Process(actual['worker_pid']).status() != psutil.STATUS_ZOMBIE
                    os.kill(os.getpid(), signal.SIGALRM)
                    return
                except (FileNotFoundError, json.JSONDecodeError):
                    if time.monotonic() > deadline:
                        notification_errors.append('real worker readiness deadline')
                        return
                    time.sleep(0.01)
        caught = None
        try:
            with QuarantineEnvironment() as quarantine:
                if os.name == 'posix':
                    notifier = threading.Thread(target=notify_on_ready)
                    notifier.start()
                else:
                    sys.settrace(cancel_at_communicate)
                try:
                    quarantine.run_command(command, timeout=10)
                except {exception_name} as error:
                    caught = error
                finally:
                    if os.name == 'posix':
                        notification_done.set()
                        notifier.join(timeout=1)
                    sys.settrace(None)
            owned = json.loads((evidence_dir / "owned.json").read_text())
            assert caught is not None and caught.args == (17,)
            assert not notification_errors
            cleanup = quarantine.cleanup_observations[-1]
            assert cleanup.owned_work_stopped and cleanup.launcher_pid == owned['launcher_pid']
            launcher_termination = assert_stopped(owned["launcher_pid"])
            worker_termination = assert_stopped(owned["worker_pid"])
            print(json.dumps({{"exception": type(caught).__name__, "args": caught.args,
                              "owned": owned, "owned_tree_stopped": True,
                              "launcher_termination": launcher_termination,
                              "worker_termination": worker_termination,
                              "cleanup_observation": cleanup.to_dict(),
                              "cancellation": "native-SIGALRM-after-real-worker-readiness" if os.name == 'posix'
                                  else "trace-at-real-communicate-entry"}}))
        finally:
            sys.settrace(None)
            notification_done.set()
            if notifier is not None:
                notifier.join(timeout=1)
            if os.name == 'posix':
                signal.signal(signal.SIGALRM, original)
    ''')
    assert observations["exception"] == exception_name


def test_registration_interruption_and_foreign_tracking_lock_are_bounded(tmp_path: Path) -> None:
    observations = _run_control(tmp_path, '''
        import json, os, signal, threading, time
        import psutil
        from ci_tools import zero_trust_runner as runner
        acquired = threading.Event()
        release = threading.Event()
        def hold():
            with runner._PROCESS_LOCK:
                acquired.set()
                release.wait(5)
        holder = threading.Thread(target=hold)
        holder.start()
        assert acquired.wait(2)
        launch_code = "import time; time.sleep(30)"
        def interrupt(signum, frame):
            raise KeyboardInterrupt("lock-control")
        original = signal.signal(signal.SIGALRM, interrupt) if os.name == 'posix' else None
        caught = None
        actual_launchers = []
        cancel = True
        def observe_registration(frame, event, arg):
            if event == 'call' and frame.f_code is runner._register_process.__code__:
                process = frame.f_locals['process']
                actual_launchers.append(process)
                (evidence_dir/'owned.json').write_text(json.dumps({'launcher_pid':process.pid}))
                if cancel:
                    sys.settrace(None)
                    if os.name == 'posix':
                        signal.setitimer(signal.ITIMER_REAL, 0.05)
                    else:
                        raise KeyboardInterrupt('lock-control')
            return None
        try:
            start = time.monotonic()
            with runner.QuarantineEnvironment() as quarantine:
                sys.settrace(observe_registration)
                try:
                    quarantine.run_command([sys.executable, "-B", "-c", launch_code], timeout=10)
                except KeyboardInterrupt as error:
                    caught = error
                finally:
                    sys.settrace(None)
                    if os.name == 'posix':
                        signal.setitimer(signal.ITIMER_REAL, 0)
            elapsed = time.monotonic() - start
            assert caught is not None and caught.args == ("lock-control",)
            assert elapsed < 2
            owned = json.loads((evidence_dir / "owned.json").read_text())
            assert actual_launchers[0].poll() is not None
            cancellation_termination = assert_stopped(owned["launcher_pid"])
            start = time.monotonic()
            assert runner.sweep_zombie_processes() == 0
            assert time.monotonic() - start < 1
            cancel = False
            with runner.QuarantineEnvironment() as quarantine:
                sys.settrace(observe_registration)
                start = time.monotonic()
                try:
                    refusal = quarantine.run_command([sys.executable, "-B", "-c", launch_code], timeout=10)
                finally:
                    sys.settrace(None)
                deadline_elapsed = time.monotonic() - start
            assert refusal.exit_code == 1 and not refusal.passed
            assert 'registration exceeded its lock deadline' in refusal.stderr
            assert deadline_elapsed < 2
            assert actual_launchers[-1].poll() is not None
            deadline_termination = assert_stopped(actual_launchers[-1].pid)
            print(json.dumps({"exception": type(caught).__name__, "duration_s": elapsed,
                              "owned": owned, "lock_wait_bounded": True,
                              "cancellation_termination": cancellation_termination,
                              "registration_deadline_elapsed": deadline_elapsed,
                              "deadline_termination": deadline_termination,
                              "cancellation": 'native-SIGALRM-during-registration' if os.name == 'posix'
                                  else 'trace-at-suspended-registration-entry'}))
        finally:
            sys.settrace(None)
            if os.name == 'posix':
                signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, original)
            release.set()
            holder.join(timeout=2)
    ''')
    assert observations["lock_wait_bounded"]


def test_import_preserves_application_signal_handlers(tmp_path: Path) -> None:
    observations = _run_control(tmp_path, '''
        import json, signal
        def application_handler(signum, frame):
            raise SystemExit(41)
        old = {sig: signal.signal(sig, application_handler) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            from ci_tools import zero_trust_runner
            assert all(signal.getsignal(sig) is application_handler for sig in old)
            print(json.dumps({"application_handlers_preserved": True}))
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)
    ''')
    assert observations["application_handlers_preserved"]


def test_mismatched_real_process_generation_is_refused_without_signalling(tmp_path: Path) -> None:
    observations = _run_control(tmp_path, '''
        import json, subprocess
        import psutil
        from ci_tools import zero_trust_runner as runner
        options = {'start_new_session':os.name == 'posix'}
        if os.name == 'nt':
            options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        owned = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"], **options)
        unrelated = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"], **options)
        try:
            other_identity = psutil.Process(unrelated.pid)
            other_identity.create_time()
            mismatched_owner = runner._ProcessOwner(True, leader=other_identity)
            assert runner._stop_owned_process(owned, mismatched_owner) is False
            assert owned.poll() is None and unrelated.poll() is None
            print(json.dumps({"real_generation_mismatch_refused": True,
                              "owned_pid": owned.pid, "unrelated_pid": unrelated.pid}))
        finally:
            for process in (owned, unrelated):
                process.kill()
                process.wait(timeout=3)
    ''')
    assert observations["real_generation_mismatch_refused"]


def test_finished_handle_retained_when_unregister_lock_is_unavailable(tmp_path: Path) -> None:
    observations = _run_control(tmp_path, '''
        import json, subprocess, threading, time
        from ci_tools import zero_trust_runner as runner
        runner._enable_owned_descendant_reaping()
        job = runner._WindowsJob() if os.name == 'nt' else None
        options = {'start_new_session':os.name == 'posix'}
        if job is not None:
            options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004
        process = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"], **options)
        owner = runner._capture_process_owner(process, os.name == 'posix', job)
        runner._register_process(process, owner)
        if job is not None:
            job.assign_and_resume(process)
        acquired = threading.Event()
        release = threading.Event()
        def hold():
            with runner._PROCESS_LOCK:
                acquired.set()
                release.wait(5)
        holder = threading.Thread(target=hold)
        holder.start()
        assert acquired.wait(2)
        try:
            assert runner._stop_owned_process(process, owner)
            start = time.monotonic()
            runner._unregister_process(process)
            elapsed = time.monotonic() - start
            assert elapsed < 1
            assert process in runner._ACTIVE_PROCESSES
            assert runner._PROCESS_OWNERS[process] is owner
            release.set()
            holder.join(timeout=2)
            runner.sweep_zombie_processes()
            assert process not in runner._ACTIVE_PROCESSES
            assert process not in runner._PROCESS_OWNERS
            print(json.dumps({"retained_until_bounded_retry": True, "duration_s": elapsed}))
        finally:
            release.set()
            holder.join(timeout=2)
            if process.poll() is None:
                process.kill()
                process.wait(timeout=3)
    ''')
    assert observations["retained_until_bounded_retry"]


def test_receipt_publication_refuses_a_non_directory(tmp_path: Path) -> None:
    target = tmp_path / "not-a-directory.txt"
    target.write_text("Actual destination refusal control.\n")
    environment = dict(os.environ, COCHEM_CI_CONTROL_EVIDENCE_DIR=str(target),
                       PYTHONPATH=str(REPOSITORY), PYTHONDONTWRITEBYTECODE="1")
    program = ("from tests.ci_tools.test_quarantine_owned_processes import _publish_control_receipt; "
               "_publish_control_receipt({'scope':'engineering-destination-control'})")
    result = subprocess.run([sys.executable, "-B", "-c", program], env=environment,
                            capture_output=True, text=True, check=False, timeout=15)
    assert result.returncode != 0
    assert "external existing regular directory" in result.stderr
    assert target.read_text() == "Actual destination refusal control.\n"


def test_stopped_context_removes_its_real_readonly_files_and_preserves_external_files(tmp_path: Path) -> None:
    observations = _run_control(tmp_path, '''
        import os, stat
        from ci_tools.zero_trust_runner import QuarantineEnvironment
        external = evidence_dir / 'external-readonly.txt'
        external.write_bytes(b'Actual external engineering input, retain unchanged.\\n')
        external.chmod(stat.S_IREAD)
        original_bytes, original_mode = external.read_bytes(), external.stat().st_mode
        with QuarantineEnvironment() as quarantine:
            root = quarantine.quarantine_dir
            owned = root / 'objects/actual-readonly-object'
            owned.parent.mkdir()
            owned.write_bytes(b'Owned immutable engineering source object.\\n')
            owned.chmod(stat.S_IREAD)
            assert not owned.stat().st_mode & stat.S_IWRITE
            result = quarantine.run_command([sys.executable, '-B', '-c', "print('actual clean exit')"], timeout=3)
            assert result.passed and result.cleanup_observation.owned_work_stopped
        assert not root.exists()
        assert external.read_bytes() == original_bytes and external.stat().st_mode == original_mode
        print(json.dumps({'owned_readonly_removed':True, 'external_bytes_and_mode_preserved':True,
                          'cleanup':result.cleanup_observation.to_dict()}))
    ''')
    assert observations['owned_readonly_removed']
    assert observations['external_bytes_and_mode_preserved']


def _run_bound_cli(root: Path, revision: str, arguments: list[str], environment: dict) -> subprocess.CompletedProcess:
    command = [sys.executable, "-B", "-m", "ci_tools.zero_trust_runner",
               "--expected-revision", revision, *arguments]
    before = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
    result = subprocess.run(command, cwd=root, env=environment, capture_output=True,
                            text=True, check=False, timeout=30)
    after = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
    assert before == after
    receipt = {
        "command": command, "returncode": result.returncode,
        "stdout": result.stdout, "stderr": result.stderr,
        "runner_sha256_before": before, "runner_sha256_after": after,
    }
    (root.parent / "bound-cli-control-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    _publish_control_receipt(receipt)
    return result


def test_cli_copies_only_reviewed_source_and_retains_external_inputs(tmp_path: Path) -> None:
    from tests.ci_tools.integrity_control_repository import repository
    root, revision = repository(tmp_path, 'def test_engineering_source():\n    assert True\n')
    (root / "student-start.xyz").write_text("Engineering input exclusion control.\n")
    (root / "private-license.txt").write_text("Engineering license-file exclusion control.\n")
    runtime = root / "ignored-runtime"
    runtime.mkdir()
    (runtime / "private-runtime.txt").write_text("Engineering runtime exclusion control.\n")
    (root / ".git/info/exclude").write_text("ignored-runtime/\n")
    external = tmp_path / "external-registry.json"
    external.write_text('{"scope":"engineering-control"}\n')
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", CONTROL_ORIGINAL_ROOT=str(root),
                       CONTROL_EXTERNAL_REGISTRY=str(external), COCHEM_CONFIG=str(external),
                       PYTEST_ADDOPTS="--unreviewed-argument", PYTEST_PLUGINS="unreviewed_plugin",
                       GIT_WORK_TREE=str(tmp_path / "unreviewed-tree"))
    environment.pop("GITHUB_SHA", None)
    program = (
        "import json,os,pathlib,sys; root=pathlib.Path.cwd(); "
        "assert str(root)!=os.environ['CONTROL_ORIGINAL_ROOT']; "
        "assert not (root/'student-start.xyz').exists(); "
        "assert not (root/'private-license.txt').exists(); "
        "assert not (root/'ignored-runtime').exists(); "
        "assert pathlib.Path(sys.argv[1]).read_text()=='Engineering input exclusion control.\\n'; "
        "assert sys.argv[2]=='--input='+str(pathlib.Path(os.environ['CONTROL_ORIGINAL_ROOT'])/'student-start.xyz'); "
        "assert pathlib.Path(sys.argv[3]).read_text()=='Engineering input exclusion control.\\n'; "
        "assert pathlib.Path(sys.argv[4]).is_relative_to(root) and pathlib.Path(sys.argv[4]).is_file(); "
        "assert all(key not in os.environ for key in ('PYTEST_ADDOPTS','PYTEST_PLUGINS','GIT_WORK_TREE')); "
        "assert os.environ['COCHEM_CONFIG']==os.environ['CONTROL_EXTERNAL_REGISTRY']; "
        "print('COPY_CONTROL: '+json.dumps({'cwd':str(root),'input':sys.argv[1],"
        "'external_registry':os.environ['COCHEM_CONFIG']}))"
    )
    result = _run_bound_cli(root, revision, ["--", sys.executable, "-B", "-c", program,
                                             str(root / "student-start.xyz"),
                                             "--input=" + str(root / "student-start.xyz"),
                                             "student-start.xyz", str(root / "ci_tools/process_runner.py")], environment)
    assert result.returncode == 0, result.stderr
    report = json.loads(next(line.removeprefix("SOURCE_BINDING_REPORT: ") for line in result.stdout.splitlines()
                             if line.startswith("SOURCE_BINDING_REPORT: ")))
    assert report["release_accepted"]
    assert report["source_before_sha256"] == report["source_after_sha256"]
    assert report["copied_before_sha256"] == report["copied_after_sha256"]
    assert report["binding"]["excluded_untracked_paths"] == [
        "ignored-runtime/private-runtime.txt", "private-license.txt", "student-start.xyz"]
    assert not report["source_changed"] and not report["copied_source_changed"]
    assert "COPY_CONTROL: " in result.stdout


@pytest.mark.parametrize("mode", ["wrong-revision", "changed-release", "changed-development"])
def test_cli_source_refusal_precedes_execution_and_development_is_nonrelease(tmp_path: Path, mode: str) -> None:
    from tests.ci_tools.integrity_control_repository import repository
    root, revision = repository(tmp_path, 'def test_engineering_source():\n    assert True\n')
    marker = tmp_path / "command-executed.txt"
    if mode != "wrong-revision":
        target = root / "ci_tools/process_runner.py"
        target.write_bytes(target.read_bytes() + b"\n# Explicit engineering development edit.\n")
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", CONTROL_MARKER=str(marker))
    environment.pop("GITHUB_SHA", None)
    program = "import os,pathlib; pathlib.Path(os.environ['CONTROL_MARKER']).write_text('executed')"
    arguments = (["--development"] if mode == "changed-development" else [])
    result = _run_bound_cli(root, "0" * 40 if mode == "wrong-revision" else revision,
                            [*arguments, "--", sys.executable, "-B", "-c", program], environment)
    if mode == "changed-development":
        assert result.returncode == 0 and marker.read_text() == "executed", result.stderr
        report = json.loads(next(line.removeprefix("SOURCE_BINDING_REPORT: ") for line in result.stdout.splitlines()
                                 if line.startswith("SOURCE_BINDING_REPORT: ")))
        assert report["binding"]["mode"] == "development" and not report["release_accepted"]
        assert report["source_before_sha256"] == report["source_after_sha256"]
        assert report["copied_before_sha256"] == report["copied_after_sha256"]
    else:
        assert result.returncode == 1 and not marker.exists(), result.stderr
        assert "[HARD_ABORT: INFRASTRUCTURE TAMPERING]" in result.stderr
        assert "SOURCE_BINDING_REPORT:" not in result.stdout
