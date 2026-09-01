"""
Physical unit tests for OS-Agnostic Telemetry Streaming & Atomic File Locking.

Invariants:
- Zero-Mock Protocol: Real filesystem I/O using pathlib.Path and filelock.FileLock.
- Concurrent multi-threaded and multi-process append operations.
- Monotonic sequence verification and lock timeout handling.
- Dynamic path resolution across environment variables.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import List

import pytest
from filelock import FileLock
from mendeleev import element

from cochem.telemetry.exceptions import TelemetryLockError
from cochem.telemetry.logger import FileLockLogger, resolve_log_path
from cochem.telemetry.schemas import TelemetryLogLevel


class TestTelemetryLocking:
    """Physical test suite for FileLockLogger and atomic telemetry concurrency."""

    def test_dynamic_mendeleev_invariants(self) -> None:
        """Verify dynamic Mendeleev invariants are operational without hardcoding."""
        oxygen = element("O")
        assert oxygen.atomic_number == 8
        assert float(oxygen.atomic_weight) > 15.9

    def test_dynamic_log_path_resolution_precedence(self) -> None:
        """Test dynamic path resolution across environment variables with safe fallback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            orig_env = {
                k: os.environ.get(k)
                for k in [
                    "COCHEM_TELEMETRY_LOG_PATH",
                    "COCHEM_LOG_DIR",
                    "COCHEM_STATE_DIR",
                    "COCH_ARTIFACTS",
                ]
            }
            try:
                # Clear all relevant env vars first
                for k in orig_env:
                    if k in os.environ:
                        del os.environ[k]

                # Test 1: Explicit path
                explicit = tmppath / "custom.log"
                res = resolve_log_path(explicit)
                assert res == explicit.resolve()

                # Test 2: COCHEM_TELEMETRY_LOG_PATH
                env_telemetry = tmppath / "env_telemetry.log"
                os.environ["COCHEM_TELEMETRY_LOG_PATH"] = str(env_telemetry)
                assert resolve_log_path(None) == env_telemetry.resolve()
                del os.environ["COCHEM_TELEMETRY_LOG_PATH"]

                # Test 3: COCHEM_LOG_DIR
                log_dir = tmppath / "logs_dir"
                os.environ["COCHEM_LOG_DIR"] = str(log_dir)
                assert resolve_log_path(None) == (log_dir / "orchestrator_wmi.log").resolve()
                del os.environ["COCHEM_LOG_DIR"]

                # Test 4: COCHEM_STATE_DIR
                state_dir = tmppath / "state_dir"
                os.environ["COCHEM_STATE_DIR"] = str(state_dir)
                assert (
                    resolve_log_path(None)
                    == (state_dir / "logs" / "orchestrator_wmi.log").resolve()
                )
                del os.environ["COCHEM_STATE_DIR"]

                # Test 5: COCH_ARTIFACTS
                artifacts_dir = tmppath / "artifacts_dir"
                os.environ["COCH_ARTIFACTS"] = str(artifacts_dir)
                assert (
                    resolve_log_path(None)
                    == (artifacts_dir / "logs" / "orchestrator_wmi.log").resolve()
                )
                del os.environ["COCH_ARTIFACTS"]

                # Test 6: Fallback relative path
                fallback = resolve_log_path(None)
                assert fallback.name == "orchestrator_wmi.log"
                assert ".cochem" in str(fallback)
            finally:
                for k, v in orig_env.items():
                    if v is not None:
                        os.environ[k] = v
                    elif k in os.environ:
                        del os.environ[k]

    def test_single_process_atomic_logging_and_sequence(self) -> None:
        """Physical test for sequential JSONL emission and monotonic sequence numbering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "telemetry_test.log"
            logger = FileLockLogger(log_path=log_path, lock_timeout=5.0)

            rec1 = logger.info("Calculation started", module="engine", job_id="job-001")
            assert rec1.seq == 0
            assert rec1.level == TelemetryLogLevel.INFO
            assert rec1.message == "Calculation started"
            assert rec1.job_id == "job-001"

            rec2 = logger.warning("High memory usage", module="engine", job_id="job-001")
            assert rec2.seq == 1
            assert rec2.level == TelemetryLogLevel.WARNING

            rec3 = logger.error("SCF convergence failure", module="dft", job_id="job-001")
            assert rec3.seq == 2
            assert rec3.level == TelemetryLogLevel.ERROR

            rec4 = logger.critical("Thermal limit exceeded", module="hardware")
            assert rec4.seq == 3
            assert rec4.level == TelemetryLogLevel.CRITICAL

            rec5 = logger.debug("Step 42 diagnostics", module="dft")
            assert rec5.seq == 4
            assert rec5.level == TelemetryLogLevel.DEBUG

            # Physical file validation
            assert log_path.exists()
            records = logger.read_records()
            assert len(records) == 5
            for idx, r in enumerate(records):
                assert r.seq == idx

            # Test start_seq filtering
            records_from_2 = logger.read_records(start_seq=2)
            assert len(records_from_2) == 3
            assert [r.seq for r in records_from_2] == [2, 3, 4]

            # Test clear
            logger.clear()
            assert len(logger.read_records()) == 0

            # Next log starts at 0 after clear
            rec_post = logger.info("Fresh log entry")
            assert rec_post.seq == 0

    def test_context_manager_protocol(self) -> None:
        """Verify context manager protocol locks and unlocks file correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "ctx_test.log"
            logger = FileLockLogger(log_path=log_path, lock_timeout=2.0)

            with logger:
                rec = logger.info("Inside context manager")
                assert rec.seq == 0

            records = logger.read_records()
            assert len(records) == 1
            assert records[0].message == "Inside context manager"

    def test_concurrent_multi_threaded_logging(self) -> None:
        """Physical concurrency test: multiple threads writing simultaneously."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "thread_concurrent.log"
            num_threads = 8
            records_per_thread = 25
            total_expected = num_threads * records_per_thread

            def _thread_worker(tid: int) -> None:
                logger = FileLockLogger(log_path=log_path, lock_timeout=10.0)
                for i in range(records_per_thread):
                    logger.info(
                        message=f"Thread {tid} entry {i}",
                        module=f"thread_{tid}",
                        metadata={"thread_id": tid, "iter": i},
                    )

            threads: List[threading.Thread] = []
            for tid in range(num_threads):
                t = threading.Thread(target=_thread_worker, args=(tid,))
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

            # Read records back and verify
            logger = FileLockLogger(log_path=log_path)
            records = logger.read_records()
            assert len(records) == total_expected

            # Verify every record is valid and sequences are strictly 0 .. total_expected - 1
            seqs = [r.seq for r in records]
            assert sorted(seqs) == list(range(total_expected))

    def test_concurrent_multi_process_logging(self) -> None:
        """Physical multi-process concurrency test: separate OS processes writing to the same log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "process_concurrent.log"
            num_processes = 4
            records_per_process = 20
            total_expected = num_processes * records_per_process

            worker_code = (
                "import sys\n"
                "from cochem.telemetry.logger import FileLockLogger\n"
                "lp = sys.argv[1]\n"
                "pid = int(sys.argv[2])\n"
                "n = int(sys.argv[3])\n"
                "logger = FileLockLogger(log_path=lp, lock_timeout=20.0)\n"
                "for i in range(n):\n"
                "    logger.info(\n"
                "        message=f'Process worker {pid} message {i}',\n"
                "        module=f'worker_{pid}',\n"
                "        job_id=f'job-{pid}',\n"
                "        metadata={'worker': pid, 'iter': i},\n"
                "    )\n"
            )

            src_dir = str(Path(__file__).resolve().parent.parent.parent / "src")
            sub_env = dict(tempfile.os.environ) if hasattr(tempfile, "os") else {}
            import os

            sub_env = os.environ.copy()
            sub_env["PYTHONPATH"] = f"{src_dir}{os.pathsep}" + sub_env.get("PYTHONPATH", "")

            procs: List[subprocess.Popen[bytes]] = []
            for pid in range(num_processes):
                p = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        worker_code,
                        str(log_path),
                        str(pid),
                        str(records_per_process),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=sub_env,
                )
                procs.append(p)

            for p in procs:
                stdout, stderr = p.communicate(timeout=30)
                assert p.returncode == 0, (
                    f"Subprocess failed with code {p.returncode}: {stderr.decode()}"
                )

            # Read back physical records and verify non-corruption
            logger = FileLockLogger(log_path=log_path)
            records = logger.read_records()
            assert len(records) == total_expected

            seqs = [r.seq for r in records]
            assert sorted(seqs) == list(range(total_expected))

    def test_lock_timeout_handling(self) -> None:
        """Verify TelemetryLockError is raised when lock cannot be acquired within timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "lock_timeout.log"
            lock_path = Path(f"{log_path}.lock")

            # Intentionally hold lock externally
            external_lock = FileLock(str(lock_path), timeout=0.1)
            external_lock.acquire()

            try:
                # Logger with very small timeout should fail
                contended_logger = FileLockLogger(log_path=log_path, lock_timeout=0.1)
                with pytest.raises(TelemetryLockError) as exc_info:
                    contended_logger.info("Should fail due to held lock")

                assert "Lock acquisition timed out" in str(exc_info.value)
            finally:
                external_lock.release()
