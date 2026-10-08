"""Real job descendants stop and are reaped on every synchronous failure path."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import pytest

CASES = (
    "stream_timeout", "communicate_timeout", "cancel", "callback_error",
    "affinity_error", "affinity_interrupt", "nonzero_exit", "decode_error",
    "stream_io_error", "shared_group", "killpg_permission", "killpg_oserror", "reap_enumeration_error", "cleanup_keyboard_interrupt",
)


def _wait_for(predicate, seconds=5):
    deadline = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("Real process did not reach the required boundary")
        time.sleep(0.005)


def _cleanup_files(directory):
    """Always clean test children, including when testing an unfixed broker."""
    for path in directory.glob("*.pid"):
        pid = int(path.read_text())
        try:
            process = psutil.Process(pid)
            process.kill()
        except psutil.NoSuchProcess:
            continue
        try:
            process.wait(timeout=2)
        except psutil.TimeoutExpired:
            # Another controller may own its waitpid; termination is still real.
            if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                raise


def _run_case(case, directory):
    from cochem_base.core_engine import cochem_core_subprocess_broker as broker

    worker_pid = directory / "worker.pid"
    launcher_pid = directory / "launcher.pid"
    progress = directory / "progress.txt"
    # The sibling deliberately shares this controller's group. Accidentally
    # signalling that group is detected by the outer, separately owned process.
    sibling = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    (directory / "sibling.pid").write_text(str(sibling.pid))
    worker = (
        "import os,pathlib,sys,time\n"
        "parent=os.getppid()\n"
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))\n"
        + ("while os.getppid()==parent: time.sleep(.005)\nprint('callback boundary',flush=True)\n"
           if case == "callback_error" else "")
        + "while True:\n pathlib.Path(sys.argv[2]).write_text(str(time.monotonic_ns()))\n time.sleep(.02)\n"
    )
    silent = case in {"nonzero_exit", "decode_error"}
    launcher = (
        "import os,pathlib,subprocess,sys,time\n"
        f"pathlib.Path({str(launcher_pid)!r}).write_text(str(os.getpid()))\n"
        f"subprocess.Popen([sys.executable,'-c',{worker!r},{str(worker_pid)!r},{str(progress)!r}]"
        + (",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL" if silent else "") + ")\n"
        f"while not pathlib.Path({str(worker_pid)!r}).exists(): time.sleep(.005)\n"
        + ("time.sleep(30)\n" if case in {"affinity_error", "affinity_interrupt", "shared_group", "stream_io_error"}
           else ("os.write(1,b'\\xff')\nos._exit(0)\n" if case == "decode_error"
                 else f"os._exit({2 if case == 'nonzero_exit' else 0})\n"))
    )
    options = dict(cwd=directory, timeout=0.8, required_disk_gb=0,
                   stream_to_disk=case not in {"communicate_timeout", "decode_error"})
    expected = subprocess.TimeoutExpired
    cancellation_thread = None
    cancellation_done = threading.Event()
    original_affinity = broker.enforce_cpu_affinity
    original_killpg = broker.os.killpg
    original_children = broker.psutil.Process.children
    original_reaper = broker._reap_owned_group_children
    original_kill_tree = broker.kill_process_tree
    cleanup_faults = []
    threads_before = set(threading.enumerate())
    if case == "cancel":
        event = threading.Event()
        options["cancellation_event"] = event
        expected = broker.SubprocessCancelledError

        def cancel_after_launcher_exit():
            while not cancellation_done.wait(.005):
                if (worker_pid.exists() and launcher_pid.exists()
                        and not psutil.pid_exists(int(launcher_pid.read_text()))):
                    event.set()
                    return

        cancellation_thread = threading.Thread(target=cancel_after_launcher_exit)
        cancellation_thread.start()
    elif case == "callback_error":
        expected = ValueError

        def reject_line(line):
            raise ValueError("Explicit test callback rejects actual worker output")

        options["on_stdout_line"] = reject_line
    elif case in {"affinity_error", "affinity_interrupt"}:
        expected = RuntimeError if case == "affinity_error" else KeyboardInterrupt

        def fail_after_real_launch(pid, cores):
            _wait_for(worker_pid.exists)
            raise expected("Explicit fault after real launcher and worker creation")

        # Fault injection affects only the affinity hook; Popen, child work,
        # ownership, signals, pipes and reaping all remain real.
        broker.enforce_cpu_affinity = fail_after_real_launch
        options["cpu_affinity"] = [psutil.Process().cpu_affinity()[0]]
    elif case == "nonzero_exit":
        expected = subprocess.CalledProcessError
    elif case == "decode_error":
        options.update(encoding="utf-8", errors="strict")
        expected = UnicodeDecodeError
    elif case == "stream_io_error":
        (directory / "process_stdout.log").mkdir()
        expected = IsADirectoryError
    elif case == "shared_group":
        options["start_new_session"] = False
    elif case in {"killpg_permission", "killpg_oserror", "cleanup_keyboard_interrupt"}:
        fault = {"killpg_permission": PermissionError, "killpg_oserror": OSError,
                 "cleanup_keyboard_interrupt": KeyboardInterrupt}[case]
        def rejected_group_signal(pid, sig):
            cleanup_faults.append("group")
            raise fault("Narrow injected cleanup failure after a real owned launch")
        broker.os.killpg = rejected_group_signal
    elif case == "reap_enumeration_error":
        # Restrict the hook to actual final reaping; initial identity collection
        # and all process creation, signals and waitpid calls remain real.
        def failed_reaper(group_id, timeout=0):
            cleanup_faults.append("reap")
            raise OSError("Narrow injected adopted-child enumeration failure")
        broker._reap_owned_group_children = failed_reaper

    def reject_numeric_tree_rediscovery(pid, timeout=10):
        raise AssertionError("Owned Popen cleanup must not rediscover an arbitrary numeric PID")
    broker.kill_process_tree = reject_numeric_tree_rediscovery
    try:
        started = time.monotonic()
        try:
            broker.safe_subprocess_run([sys.executable, "-c", launcher], **options)
        except expected:
            pass
        else:
            raise AssertionError("Expected native failure was not reported")
        assert time.monotonic() - started < 8
        assert sibling.poll() is None, "Unrelated sibling was terminated"
        if case in {"killpg_permission", "killpg_oserror", "cleanup_keyboard_interrupt", "reap_enumeration_error"}:
            assert cleanup_faults, "The secondary cleanup fault must actually be exercised"
        if case != "stream_io_error":
            assert worker_pid.exists(), "The regression requires a real running descendant"
        # Linux subreaping must remove the actual PID, not merely leave a zombie.
        for path in (worker_pid, launcher_pid):
            if path.exists():
                assert not psutil.pid_exists(int(path.read_text())), path.name
        cancellation_done.set()
        if cancellation_thread:
            cancellation_thread.join(timeout=1)
        assert set(threading.enumerate()) <= threads_before, "Output reader outlived failed execution"
        before = progress.read_bytes() if progress.exists() else None
        time.sleep(.06)
        assert (progress.read_bytes() if progress.exists() else None) == before
        print(json.dumps({"case": case, "descendants_reaped": True,
                          "output_readers_stopped": True, "unrelated_sibling_alive": True}))
    finally:
        broker.enforce_cpu_affinity = original_affinity
        broker.os.killpg = original_killpg
        broker.psutil.Process.children = original_children
        broker._reap_owned_group_children = original_reaper
        broker.kill_process_tree = original_kill_tree
        cancellation_done.set()
        if cancellation_thread:
            cancellation_thread.join(timeout=1)
        _cleanup_files(directory)
        sibling.wait(timeout=2)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Verifies Linux adopted-child reaping and POSIX group ownership")
@pytest.mark.parametrize("case", CASES)
def test_real_failure_reaps_owned_descendants_without_signalling_siblings(tmp_path, case):
    repository = Path(__file__).resolve().parents[2]
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1",
                       PYTHONPATH=os.pathsep.join((str(repository / "src"), str(repository))))
    try:
        result = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), case, str(tmp_path)],
                                cwd=repository, env=environment, capture_output=True, text=True,
                                start_new_session=True, timeout=20)
        assert result.returncode == 0, result.stdout + result.stderr
        receipt = json.loads(result.stdout.strip().splitlines()[-1])
        assert receipt == {"case": case, "descendants_reaped": True,
                           "output_readers_stopped": True, "unrelated_sibling_alive": True}
    finally:
        _cleanup_files(tmp_path)


if __name__ == "__main__":
    _run_case(sys.argv[1], Path(sys.argv[2]))


@pytest.mark.parametrize('failure', ['create', 'kill_flag', 'assign', 'resume_status', 'resume_exception'])
def test_windows_setup_failure_contract_never_leaves_a_started_child(tmp_path, monkeypatch, failure):
    """Win32 API doubles test fail-closed control flow; child lifecycle is real Linux.

    This is not native Windows Job Object acceptance. No successful Windows
    containment result is manufactured by these explicit failure injections.
    """
    if sys.platform == 'win32':
        pytest.skip('This mixed API-double/real-child regression is POSIX infrastructure only')
    from types import SimpleNamespace

    from cochem_base.core_engine import cochem_core_subprocess_broker as broker

    children = []
    closes = []
    real_popen = subprocess.Popen

    class JobFailureFixture:
        handle = None if failure == 'create' else 123
        kill_on_close_enabled = failure != 'kill_flag'
        def assign_popen(self, proc):
            assert proc in children
            return failure != 'assign'
        def close(self):
            closes.append(True)

    def launch_real_posix_child(command, **kwargs):
        assert kwargs.pop('creationflags') & 0x00000004  # suspended Windows intent
        kwargs['start_new_session'] = True
        child = real_popen(command, **kwargs)
        child._handle = child.pid  # API-double argument only, never a native handle claim
        children.append(child)
        return child

    def fail_resume(handle):
        assert children and handle == children[0].pid
        if failure == 'resume_exception':
            raise RuntimeError('Explicit injected Windows resume exception')
        return 0xC0000001

    monkeypatch.setattr(broker.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(broker, 'WindowsJobObject', JobFailureFixture)
    monkeypatch.setattr(broker.subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x00000200, raising=False)
    monkeypatch.setattr(broker.subprocess, 'Popen', launch_real_posix_child)
    monkeypatch.setattr(broker.ctypes, 'windll', SimpleNamespace(ntdll=SimpleNamespace(NtResumeProcess=fail_resume)), raising=False)
    expected = RuntimeError if failure == 'resume_exception' else OSError
    try:
        with pytest.raises(expected, match='Windows|NTSTATUS'):
            broker.safe_subprocess_run([sys.executable, '-I', '-c', 'import time; time.sleep(30)'],
                                       cwd=tmp_path, required_disk_gb=0, timeout=3)
        assert bool(children) == (failure not in {'create', 'kill_flag'})
        assert closes
        for child in children:
            assert child.returncode is not None
            assert not psutil.pid_exists(child.pid)
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=2)


@pytest.mark.parametrize('outcome', [True, False, 'error'])
def test_windows_assignment_uses_original_process_handle(outcome, monkeypatch):
    """Explicit Win32 API transport double; no native Windows success claim."""
    from types import SimpleNamespace

    from cochem_base.core_engine import cochem_core_subprocess_broker as broker
    calls = []
    def assign(job_handle, process_handle):
        calls.append((job_handle, process_handle))
        if outcome == 'error':
            raise OSError('Explicit Windows assignment API failure')
        return outcome
    job = broker.WindowsJobObject.__new__(broker.WindowsJobObject)
    job._is_windows = True
    job.handle = 123
    proc = SimpleNamespace(pid=999, _handle=456)
    monkeypatch.setattr(broker.ctypes, 'windll', SimpleNamespace(kernel32=SimpleNamespace(AssignProcessToJobObject=assign)), raising=False)
    assert job.assign_popen(proc) is (outcome is True)
    assert calls == [(123, 456)]
