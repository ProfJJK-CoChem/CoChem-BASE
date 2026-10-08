"""Genuine subprocess controls for quarantine lifetime ownership.

These controls execute on the native POSIX host. They do not substitute a
Windows API, process identity or scientific calculation with a test double.
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

import pytest

REPOSITORY = Path(__file__).resolve().parents[2]
RUNNER = REPOSITORY / "ci_tools" / "zero_trust_runner.py"


def _run_control(tmp_path: Path, body: str) -> dict:
    before = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
    control = tmp_path / "control.py"
    control.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(REPOSITORY)!r})\n"
        "from pathlib import Path\n"
        f"evidence_dir = Path({str(tmp_path)!r})\n"
        + textwrap.dedent(body), encoding="utf-8",
    )
    start = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, "-B", str(control)], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True,
    )
    forced_cleanup = False
    try:
        stdout, stderr = process.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        forced_cleanup = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=3)
    finally:
        # Any failed control's explicit owned group is removed by its controller,
        # without turning forced cleanup into a passing lifetime observation.
        owned_path = tmp_path / "owned.json"
        if owned_path.exists():
            group_id = json.loads(owned_path.read_text())["launcher_pid"]
            try:
                os.killpg(group_id, 0)
            except ProcessLookupError:
                group_id = None
            if group_id is not None:
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
    assert before == after
    assert not forced_cleanup, receipt
    assert process.returncode == 0, receipt
    observations = json.loads(stdout.strip().splitlines()[-1])
    receipt["observations"] = observations
    (tmp_path / "control-receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8",
    )
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
        tracker_pid = resource_tracker._resource_tracker._pid
        unrelated = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"])
        owned_status = subprocess.Popen([sys.executable, "-B", "-c", "raise SystemExit(7)"])
        original_umask = os.umask(0)
        worker_code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
        launch_code = (
            "import json,os,subprocess,sys; from pathlib import Path; "
            + "child=subprocess.Popen([sys.executable,'-B','-c'," + repr(worker_code) + "]"
            + ("" if {inherit_pipes!r} else ",stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL")
            + "); Path(" + repr(str(evidence_dir / "owned.json")) + ").write_text(json.dumps("
            + "{{'launcher_pid':os.getpid(),'worker_pid':child.pid}})); raise SystemExit({exit_code})"
        )
        try:
            start = time.monotonic()
            with QuarantineEnvironment() as quarantine:
                assert stat.S_IMODE(quarantine.quarantine_dir.stat().st_mode) == 0o700
                copied_source = evidence_dir / "copied-source"
                copied_source.mkdir(mode=0o755)
                shutil.copytree(copied_source, quarantine.quarantine_dir, dirs_exist_ok=True)
                assert stat.S_IMODE(quarantine.quarantine_dir.stat().st_mode) == 0o755
                result = quarantine.run_command([sys.executable, "-B", "-c", launch_code], timeout=1)
                assert stat.S_IMODE(quarantine.quarantine_dir.stat().st_mode) == 0o700
            owned = json.loads((evidence_dir / "owned.json").read_text())
            assert not psutil.pid_exists(owned["worker_pid"]), owned
            assert unrelated.poll() is None
            assert owned_status.wait(timeout=3) == 7
            assert psutil.pid_exists(tracker_pid)
            if {inherit_pipes!r}:
                assert result.exit_code == 124 and result.timed_out and not result.passed
            else:
                assert result.exit_code == {exit_code} and not result.timed_out
                assert result.passed is ({exit_code} == 0)
            assert time.monotonic() - start < 6
            print(json.dumps({{"result": result.to_dict(), "owned": owned,
                              "unrelated_survived": True, "tracker_survived": True,
                              "quarantine_mode": "0700", "controller_umask": "0000",
                              "copied_root_mode_repaired": True,
                              "other_popen_status": 7}}))
        finally:
            os.umask(original_umask)
            unrelated.kill()
            unrelated.wait(timeout=3)
            if owned_status.poll() is None:
                owned_status.kill()
                owned_status.wait(timeout=3)
            tracker_memory.close()
            tracker_memory.unlink()
    ''')
    assert observations["unrelated_survived"] and observations["tracker_survived"]


@pytest.mark.parametrize("exception_name", ["KeyboardInterrupt", "SystemExit"])
def test_interruption_preserves_original_exception_and_stops_owned_tree(
    tmp_path: Path, exception_name: str,
) -> None:
    observations = _run_control(tmp_path, f'''
        import json, os, signal, subprocess, time
        import psutil
        from ci_tools.zero_trust_runner import QuarantineEnvironment
        worker_code = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)"
        launch_code = (
            "import json,os,subprocess,sys,time; from pathlib import Path; "
            + "child=subprocess.Popen([sys.executable,'-B','-c'," + repr(worker_code) + "]); "
            + "Path(" + repr(str(evidence_dir / "owned.json")) + ").write_text(json.dumps("
            + "{{'launcher_pid':os.getpid(),'worker_pid':child.pid}})); time.sleep(30)"
        )
        def interrupt(signum, frame):
            raise {exception_name}(17)
        original = signal.signal(signal.SIGALRM, interrupt)
        caught = None
        try:
            with QuarantineEnvironment() as quarantine:
                signal.setitimer(signal.ITIMER_REAL, 0.4)
                try:
                    quarantine.run_command([sys.executable, "-B", "-c", launch_code], timeout=10)
                except {exception_name} as error:
                    caught = error
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
            owned = json.loads((evidence_dir / "owned.json").read_text())
            assert caught is not None and caught.args == (17,)
            assert not psutil.pid_exists(owned["launcher_pid"])
            assert not psutil.pid_exists(owned["worker_pid"])
            print(json.dumps({{"exception": type(caught).__name__, "args": caught.args,
                              "owned": owned, "owned_tree_stopped": True}}))
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
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
        launch_code = (
            "import json,os,time; from pathlib import Path; Path("
            + repr(str(evidence_dir / "owned.json"))
            + ").write_text(json.dumps({'launcher_pid':os.getpid()})); time.sleep(30)"
        )
        def interrupt(signum, frame):
            raise KeyboardInterrupt("lock-control")
        original = signal.signal(signal.SIGALRM, interrupt)
        caught = None
        try:
            start = time.monotonic()
            with runner.QuarantineEnvironment() as quarantine:
                signal.setitimer(signal.ITIMER_REAL, 0.15)
                try:
                    quarantine.run_command([sys.executable, "-B", "-c", launch_code], timeout=10)
                except KeyboardInterrupt as error:
                    caught = error
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
            elapsed = time.monotonic() - start
            assert caught is not None and caught.args == ("lock-control",)
            assert elapsed < 2
            owned = json.loads((evidence_dir / "owned.json").read_text())
            assert not psutil.pid_exists(owned["launcher_pid"])
            start = time.monotonic()
            assert runner.sweep_zombie_processes() == 0
            assert time.monotonic() - start < 1
            print(json.dumps({"exception": type(caught).__name__, "duration_s": elapsed,
                              "owned": owned, "lock_wait_bounded": True}))
        finally:
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
        owned = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"],
                                 start_new_session=True)
        unrelated = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"],
                                     start_new_session=True)
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
        process = subprocess.Popen([sys.executable, "-B", "-c", "import time; time.sleep(30)"],
                                   start_new_session=True)
        owner = runner._capture_process_owner(process, True)
        runner._register_process(process, owner)
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


def _run_bound_cli(root: Path, revision: str, arguments: list[str], environment: dict) -> subprocess.CompletedProcess:
    command = [sys.executable, "-B", "-m", "ci_tools.zero_trust_runner",
               "--expected-revision", revision, *arguments]
    before = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
    result = subprocess.run(command, cwd=root, env=environment, capture_output=True,
                            text=True, check=False, timeout=30)
    after = hashlib.sha256(RUNNER.read_bytes()).hexdigest()
    assert before == after
    (root.parent / "bound-cli-control-receipt.json").write_text(json.dumps({
        "command": command, "returncode": result.returncode,
        "stdout": result.stdout, "stderr": result.stderr,
        "runner_sha256_before": before, "runner_sha256_after": after,
    }, indent=2) + "\n", encoding="utf-8")
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
        "assert sys.argv[2]=='--input='+os.environ['CONTROL_ORIGINAL_ROOT']+'/student-start.xyz'; "
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
