"""Real child-process crashes must leave exact, immutable forensic evidence."""

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import psutil
import pytest

from cochem_base.core_engine.cochem_core_subprocess_broker import safe_subprocess_run


def _assert_record(record, directory, stderr):
    target = Path(record["record_path"])
    assert target.parent == directory.resolve()
    assert target.is_file() and target.stat().st_mode & 0o222 == 0
    stored = json.loads(target.read_text())
    assert stored["event"] == "process_crash"
    assert stored["stderr_tail_hex"] == stderr[-256:].hex()
    assert stored["stderr_tail_bytes"] == len(stderr[-256:])
    assert stored["binary_path"] == str(Path(sys.executable).resolve())
    with open(sys.executable, "rb") as executable:
        assert stored["binary_sha256"] == hashlib.file_digest(executable, "sha256").hexdigest()
    assert stored["git_provenance"]["status"] == "available"
    assert len(stored["git_commit_object_sha256"]) == 64
    from cochem_base._version import get_version
    from cochem_base.core_engine import crash_provenance
    assert stored["source_identity"]["package_version"] == get_version()
    assert stored["source_identity"]["recorder_module_sha256"] == hashlib.sha256(Path(crash_provenance.__file__).read_bytes()).hexdigest()
    assert stored["ram_used_bytes"] > 0 and stored["ram_available_bytes"] > 0
    assert stored["resource_observation"] == "system_at_crash_recording"
    digest = stored.pop("sha256")
    assert hashlib.sha256(json.dumps(stored, sort_keys=True, separators=(",", ":")).encode()).hexdigest() == digest
    assert digest == record["sha256"]
    return stored


@pytest.mark.parametrize("streamed", [False, True])
@pytest.mark.parametrize("checked", [False, True])
def test_native_text_crash_preserves_invalid_utf8_before_decoding(tmp_path, streamed, checked):
    stderr = bytes(range(256)) * 3 + b"\xff\xfe\x00terminal bytes\r\n"
    command = [sys.executable, "-c", f"import os; os.write(2,{stderr!r}); os._exit(139)"]
    callbacks = []
    options = dict(cwd=tmp_path, required_disk_gb=0, text=True, check=checked,
                   stream_to_disk=streamed, encoding="utf-8", errors="strict")
    if streamed:
        options["on_stdout_line"] = callbacks.append
    if checked:
        with pytest.raises(subprocess.CalledProcessError) as failed:
            safe_subprocess_run(command, **options)
        result = failed.value
    else:
        result = safe_subprocess_run(command, **options)
    assert result.returncode == 139
    assert isinstance(result.stderr, str)
    assert result.hex_dump == stderr[-256:].hex()
    record = _assert_record(result.crash_record, tmp_path / "CrashRecords", stderr)
    assert record["inputs"] == command
    assert result.crash_payload["record_path"] == result.crash_record["record_path"]
    assert result.crash_payload["record_sha256"] == result.crash_record["sha256"]
    assert len(list((tmp_path / "CrashRecords").glob("crash-*.json"))) == 1
    if streamed:
        assert (tmp_path / "process_stderr.log").read_bytes() == stderr


@pytest.mark.parametrize("streamed", [False, True])
def test_native_binary_crash_records_exact_short_tail_without_padding(tmp_path, streamed):
    stderr = b"\xff\x00\xfe\r\nfatal"
    result = safe_subprocess_run(
        [sys.executable, "-c", f"import os; os.write(2,{stderr!r}); os._exit(139)"],
        cwd=tmp_path, required_disk_gb=0, text=False, check=False, stream_to_disk=streamed,
    )
    assert result.stderr == stderr
    _assert_record(result.crash_record, tmp_path / "CrashRecords", stderr)


def test_crash_records_actual_prelaunch_inputs_and_child_resource_controls(tmp_path):
    deck = tmp_path / "calculation.inp"
    original = b"! HF STO-3G\n* xyz 0 1\nH 0 0 0\nH 0 0 .74\n*\n"
    deck.write_bytes(original)
    script = tmp_path / "fatal_child.py"
    script.write_text("import os,pathlib,sys\npathlib.Path(sys.argv[1]).write_text('changed during run')\n"
                      "os.write(2,b'fatal native boundary')\nos._exit(139)\n")
    environment = dict(os.environ, OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="1",
                       COCHEM_BOUNDARY_PRIVATE_VALUE="not-a-real-credential-do-not-record")
    result = safe_subprocess_run([sys.executable, str(script), str(deck)], cwd=tmp_path,
                                env=environment, required_disk_gb=0, check=False, sanitize_mpi=False)
    stored = _assert_record(result.crash_record, tmp_path / "CrashRecords", b"fatal native boundary")
    files = {item["path"]: item for item in stored["input_files"]}
    assert files[str(deck)]["sha256"] == hashlib.sha256(original).hexdigest()
    assert files[str(deck)]["size_bytes"] == len(original)
    assert deck.read_text() == "changed during run"
    assert stored["input_identity_observed"] == "before_launch"
    assert stored["working_directory"] == str(tmp_path)
    assert stored["requested_resources"]["thread_environment"]["OMP_NUM_THREADS"] == "2"
    assert stored["requested_resources"]["thread_environment"]["OPENBLAS_NUM_THREADS"] == "1"
    assert "not-a-real-credential-do-not-record" not in json.dumps(stored)


def test_cfour_style_implicit_zmat_is_bound_without_command_argument(tmp_path):
    zmat = tmp_path / "ZMAT"
    zmat.write_text("H2 boundary input\nH 0 0 0\nH 0 0 1.4\n")
    result = safe_subprocess_run([sys.executable, "-c", "import os; os._exit(139)"],
                                cwd=tmp_path, required_disk_gb=0, check=False)
    record = _assert_record(result.crash_record, tmp_path / "CrashRecords", b"")
    assert record["input_files"] == [{"path": str(zmat), "size_bytes": zmat.stat().st_size,
                                     "sha256": hashlib.sha256(zmat.read_bytes()).hexdigest()}]


def test_repeated_native_crashes_create_distinct_immutable_records(tmp_path):
    directory = tmp_path / "persistent-crashes"
    records = [safe_subprocess_run([sys.executable, "-c", "import os; os._exit(139)"],
                                  cwd=tmp_path, required_disk_gb=0, check=False,
                                  crash_log_directory=directory).crash_record for _ in range(2)]
    assert records[0]["record_path"] != records[1]["record_path"]
    assert len(list(directory.glob("crash-*.json"))) == 2
    for record in records:
        _assert_record(record, directory, b"")


def test_normal_failure_and_success_do_not_claim_native_crash(tmp_path):
    for code in (0, 2):
        result = safe_subprocess_run([sys.executable, "-c", f"raise SystemExit({code})"],
                                    cwd=tmp_path, required_disk_gb=0, check=False)
        assert result.returncode == code and result.crash_record is None
        assert result.crash_payload["is_crash"] is False
    assert not (tmp_path / "CrashRecords").exists()


def test_exported_core_broker_uses_same_exact_immutable_recorder(tmp_path):
    from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessBroker
    stderr = bytes(range(256)) * 2 + b"\xff\x00\xfe"
    with SubprocessBroker(cwd=tmp_path) as broker:
        code = broker.execute([sys.executable, "-c", f"import os; os.write(2,{stderr!r}); os._exit(139)"],
                              job_name="native-byte-boundary", required_disk_gb=0.01)
        assert code == 139
        _assert_record(broker.last_crash_record, tmp_path / "CrashRecords", stderr)
        assert len(list((tmp_path / "CrashRecords").glob("crash-*.json"))) == 1


def test_canonical_object_broker_binds_actual_child_cwd_inputs(tmp_path):
    from cochem.concurrency.subprocess_broker import SubprocessBroker
    work = tmp_path / "job"
    work.mkdir()
    deck = work / "ZMAT"
    deck.write_bytes(b"implicit native input\n")
    broker = SubprocessBroker(base_scratch_dir=tmp_path / "scratch", max_retries=3)
    broker.store_dir = tmp_path / "published"
    result = broker.execute([sys.executable, "-c", "import os; os._exit(139)"], cwd=work)
    record = _assert_record(result.crash_diagnostics, tmp_path / "published" / "Logs", b"")
    assert record["working_directory"] == str(work)
    assert record["input_files"] == [{"path": str(deck), "size_bytes": deck.stat().st_size,
                                     "sha256": hashlib.sha256(deck.read_bytes()).hexdigest()}]


@pytest.mark.parametrize("stderr", [b"", b"\xff\x00\xfe\r\n"])
def test_readonly_telemetry_log_never_synthesizes_native_stderr(tmp_path, stderr):
    from cochem_base.core_engine.cochem_core_telemetry_logger import TelemetryLogger
    with TelemetryLogger(log_dir=tmp_path) as logger:
        target = logger.aggregate_and_lock("short-native-tail", [], [], 139, "identity", stderr_bytes=stderr)
    content = Path(target).read_text()
    assert f"Captured tail bytes: {len(stderr)}; source: raw process bytes" in content
    assert "Segmentation fault (core dumped)" not in content
    if stderr:
        assert "0x0000: " + stderr.hex(" ") in content
        assert "0x0010:" not in content
    else:
        assert "0x0000:" not in content


@pytest.mark.skipif(os.name == "nt", reason="This case verifies an owned POSIX process group")
@pytest.mark.parametrize("broker_kind", ["safe", "core"])
def test_crashed_launcher_reaps_pipe_holding_worker_before_recording(tmp_path, broker_kind):
    pid_file = tmp_path / "worker.pid"
    worker = ("import os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); "
              "time.sleep(30)")
    launcher = (
        "import os,pathlib,subprocess,sys,time; "
        f"child=subprocess.Popen([sys.executable,'-c',{worker!r},{str(pid_file)!r}]); "
        f"target=pathlib.Path({str(pid_file)!r}); "
        "\nwhile not target.exists(): time.sleep(.005)\n"
        "os.write(2,b'launcher actual fatal tail'); os._exit(139)"
    )
    started = time.monotonic()
    if broker_kind == "safe":
        result = safe_subprocess_run([sys.executable, "-c", launcher], cwd=tmp_path,
                                    timeout=10, required_disk_gb=0, check=False, stream_to_disk=True)
        assert result.returncode == 139
        record = result.crash_record
    else:
        from cochem_base.core_engine.cochem_core_subprocess_broker import SubprocessBroker
        with SubprocessBroker(cwd=tmp_path) as broker:
            assert broker.execute([sys.executable, "-c", launcher], timeout=10,
                                  job_name="fatal-worker-boundary", required_disk_gb=0.01) == 139
            record = broker.last_crash_record
    assert time.monotonic() - started < 5
    _assert_record(record, tmp_path / "CrashRecords", b"launcher actual fatal tail")
    assert not psutil.pid_exists(int(pid_file.read_text()))


@pytest.mark.skipif(os.name == "nt", reason="POSIX signal termination is unavailable on native Windows")
def test_actual_sigabrt_is_intercepted_not_just_numeric_exit_status(tmp_path):
    script = ("import os,resource,signal; resource.setrlimit(resource.RLIMIT_CORE,(0,0)); "
              "os.write(2,b'actual SIGABRT boundary'); os.kill(os.getpid(),signal.SIGABRT)")
    result = safe_subprocess_run([sys.executable, "-c", script], cwd=tmp_path,
                                required_disk_gb=0, check=False, stream_to_disk=True)
    assert result.returncode == -signal.SIGABRT
    assert result.crash_payload["crash_type"] == "SIGABRT"
    _assert_record(result.crash_record, tmp_path / "CrashRecords", b"actual SIGABRT boundary")
