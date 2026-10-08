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
    "callback_interrupt", "nonzero_exit", "decode_error", "stream_io_error",
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
            generation_file = Path(str(path) + ".ctime")
            if not generation_file.is_file() or process.create_time() != float(generation_file.read_text()):
                raise AssertionError("Refusing to clean a process without its captured creation identity")
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
    (directory / "sibling.pid.ctime").write_text(str(psutil.Process(sibling.pid).create_time()))
    (directory / "sibling.pid").write_text(str(sibling.pid))
    worker = (
        "import os,pathlib,psutil,sys,time\n"
        "parent=os.getppid()\n"
        "pathlib.Path(sys.argv[1]+'.ctime').write_text(str(psutil.Process().create_time()))\n"
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid()))\n"
        + ("while os.getppid()==parent: time.sleep(.005)\nprint('callback boundary',flush=True)\n"
           if case in {"callback_error", "callback_interrupt"} else "")
        + "while True:\n pathlib.Path(sys.argv[2]).write_text(str(time.monotonic_ns()))\n time.sleep(.02)\n"
    )
    silent = case in {"nonzero_exit", "decode_error"}
    launcher = (
        "import os,pathlib,psutil,subprocess,sys,time\n"
        f"pathlib.Path({str(launcher_pid) + '.ctime'!r}).write_text(str(psutil.Process().create_time()))\n"
        f"pathlib.Path({str(launcher_pid)!r}).write_text(str(os.getpid()))\n"
        f"subprocess.Popen([sys.executable,'-c',{worker!r},{str(worker_pid)!r},{str(progress)!r}]"
        + (",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL" if silent else "") + ")\n"
        f"while not pathlib.Path({str(worker_pid)!r}).exists(): time.sleep(.005)\n"
        + ("time.sleep(30)\n" if case == "stream_io_error"
           else ("os.write(1,b'\\xff')\nos._exit(0)\n" if case == "decode_error"
                 else f"os._exit({2 if case == 'nonzero_exit' else 0})\n"))
    )
    options = dict(cwd=directory, timeout=0.8, required_disk_gb=0,
                   stream_to_disk=case not in {"communicate_timeout", "decode_error"})
    expected = subprocess.TimeoutExpired
    cancellation_thread = None
    cancellation_done = threading.Event()
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
    elif case in {"callback_error", "callback_interrupt"}:
        expected = ValueError if case == "callback_error" else KeyboardInterrupt

        def reject_line(line):
            raise expected("Application callback rejects actual worker output")

        options["on_stdout_line"] = reject_line
    elif case == "nonzero_exit":
        expected = subprocess.CalledProcessError
    elif case == "decode_error":
        options.update(encoding="utf-8", errors="strict")
        expected = UnicodeDecodeError
    elif case == "stream_io_error":
        (directory / "process_stdout.log").mkdir()
        expected = IsADirectoryError
    try:
        started = time.monotonic()
        try:
            broker.safe_subprocess_run([sys.executable, "-c", launcher], **options)
        except expected as error:
            if case in {"callback_error", "callback_interrupt"}:
                assert str(error) == "Application callback rejects actual worker output"
            elif case == "nonzero_exit":
                assert error.returncode == 2
            elif case in {"stream_timeout", "communicate_timeout"}:
                assert error.timeout == options["timeout"]
        else:
            raise AssertionError("Expected native failure was not reported")
        assert time.monotonic() - started < 8
        assert sibling.poll() is None, "Unrelated sibling was terminated"
        if case != "stream_io_error":
            assert worker_pid.exists(), "The regression requires a real running descendant"
        # Linux requires collection. Other hosts preserve terminal observations
        # separately when the external reaper still owns collection.
        terminal_pending = []
        for path in (worker_pid, launcher_pid):
            if path.exists():
                pid = int(path.read_text())
                if sys.platform.startswith("linux"):
                    assert not psutil.pid_exists(pid), path.name
                else:
                    try:
                        member = psutil.Process(pid)
                        generation = member.create_time()
                        assert generation == float(Path(str(path) + ".ctime").read_text()), path.name
                        status = member.status()
                        assert member.is_running(), "Terminal observation lost its captured generation"
                    except psutil.NoSuchProcess:
                        continue
                    assert status in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}, path.name
                    terminal_pending.append({"pid": pid, "create_time": generation,
                                             "status": status, "collection": "external-reaper-pending"})
        cancellation_done.set()
        if cancellation_thread:
            cancellation_thread.join(timeout=1)
        assert set(threading.enumerate()) <= threads_before, "Output reader outlived failed execution"
        before = progress.read_bytes() if progress.exists() else None
        time.sleep(.06)
        assert (progress.read_bytes() if progress.exists() else None) == before
        print(json.dumps({"case": case, "descendants_terminal": True,
                          "descendants_reaped": not terminal_pending,
                          "terminal_pending": terminal_pending,
                          "output_readers_stopped": True, "unrelated_sibling_alive": True}))
    finally:
        cancellation_done.set()
        if cancellation_thread:
            cancellation_thread.join(timeout=1)
        _cleanup_files(directory)
        sibling.wait(timeout=2)


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
        assert receipt["case"] == case and receipt["descendants_terminal"] is True
        assert receipt["output_readers_stopped"] is True and receipt["unrelated_sibling_alive"] is True
        assert receipt["descendants_reaped"] == (not receipt["terminal_pending"])
        if sys.platform.startswith("linux"):
            assert receipt["descendants_reaped"] is True and receipt["terminal_pending"] == []
    finally:
        _cleanup_files(tmp_path)


if __name__ == "__main__":
    _run_case(sys.argv[1], Path(sys.argv[2]))


def test_native_job_admission_and_closed_job_refusal_use_actual_process(tmp_path):
    """Exercise Win32 only on Windows; other hosts verify explicit absence."""
    from cochem_base.core_engine import cochem_core_subprocess_broker as broker

    job = broker.WindowsJobObject()
    options = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000004
    child = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(30)"],
                             cwd=tmp_path, **options)
    try:
        if os.name == "nt":
            assert job.handle
            assert job.assign_popen(child)
            broker._resume_owned_windows_process(child)
            assert child.poll() is None
            job.close()
            assert child.wait(timeout=3) is not None
        else:
            assert job.handle is None
            assert not job.assign_popen(child)
            assert child.poll() is None
        job.close()
        assert not job.assign_popen(child)
    finally:
        job.close()
        if child.poll() is None:
            child.kill()
        child.wait(timeout=3)


def test_native_affinity_rejects_an_actual_collected_process(tmp_path):
    from cochem_base.core_engine import cochem_core_subprocess_broker as broker

    child = subprocess.Popen([sys.executable, "-I", "-c", "raise SystemExit(17)"], cwd=tmp_path)
    assert child.wait(timeout=3) == 17
    assert not broker.enforce_cpu_affinity(child.pid, [0])
