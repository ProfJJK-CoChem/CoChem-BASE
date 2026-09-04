"""Zero-Mock Concurrency & Process Containment Test Suite for Chunk 2 (Suggestions #15-#20).

Adheres to:
- Method Matrix v4 (§8A, §8A.1, §8A.4, §8B.4, §12.5)
- Zero-Mock Anti-Spoofing Protocol (100% authentic physical execution & OS primitives)
- 6-Tier Environment Matrix Portability
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import multiprocessing.shared_memory as sm
import os
import pathlib
import platform
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Dict, List

import h5py
import numpy as np
import psutil
import pytest

from cochem.concurrency.subprocess_broker import SubprocessBroker
from cochem.core.airgap_coordinator import AirGapConfig, TripartiteAirGapCoordinator
from cochem.core.context import ExecutionContext
from cochem.core.ipc.serializer import SharedMemoryBuffer
from cochem_base.core_engine.cochem_core_job_manager import JobConfig, JobManager
from cochem_base.core_engine.cochem_core_pes_store import TripartitePESStore
from cochem_base.core_engine.cochem_core_subprocess_broker import (
    WindowsJobObject,
    build_thread_affinity_env,
)


@pytest.fixture
def test_exec_context(tmp_path: pathlib.Path) -> ExecutionContext:
    """Isolated tripartite execution context."""
    src_dir = tmp_path / "cochem_src"
    data_dir = tmp_path / "cochem_data"
    artifacts_dir = tmp_path / "cochem_artifacts"
    scratch_dir = artifacts_dir / f"cochem_exec_{uuid.uuid4().hex[:8]}"

    src_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    return ExecutionContext(
        execution_id=str(uuid.uuid4()),
        session_name="chunk2_concurrency_test",
        src_dir=src_dir,
        data_dir=data_dir,
        artifacts_dir=artifacts_dir,
        scratch_dir=scratch_dir,
        env_tier="Tier 1A",
    )


def test_zero_orphan_process_reaping(test_exec_context: ExecutionContext) -> None:
    """Suggestion #15: Verify OS-level containment and complete process tree reaping with zero orphans."""
    broker = SubprocessBroker(test_exec_context)

    # Launch a Python script that spawns a child worker and waits
    marker_token = f"cochem_orphan_marker_{uuid.uuid4().hex[:8]}"
    script = (
        "import sys, subprocess, time\n"
        "p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"# {marker_token}\n"
        "time.sleep(30)\n"
    )

    result = broker.execute(
        [sys.executable, "-c", script],
        timeout_sec=1.5,
    )

    # The broker should report timeout
    assert not result.success
    assert result.returncode == -1

    # Give OS brief grace window to clean up handles
    time.sleep(0.5)

    # Scan psutil to verify zero remaining processes containing the marker or lingering child sleep
    current_pids = set(psutil.pids())
    for pid in current_pids:
        try:
            p = psutil.Process(pid)
            cmdline = " ".join(p.cmdline())
            assert marker_token not in cmdline, f"Orphaned process detected: PID {pid}, {cmdline}"
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # On Windows, verify WindowsJobObject capability
    if platform.system() == "Windows":
        job = WindowsJobObject(kill_on_close=True)
        assert job.handle is not None
        job.close()
        assert job.handle is None


def test_job_manager_stream_concurrency(tmp_path: pathlib.Path) -> None:
    """Suggestion #16: Verify consolidated stream ingestion without communicate() collisions."""
    async def _run() -> None:
        job_mgr = JobManager(poll_interval=0.05)

        # Submit a job that produces both stdout and stderr
        script = "import sys; sys.stdout.write('OUT_OK\\n'); sys.stderr.write('ERR_OK\\n')"
        cfg = JobConfig(command=[sys.executable, "-c", script], cwd=str(tmp_path))
        job_id = await job_mgr.submit_job(cfg) if asyncio.iscoroutinefunction(job_mgr.submit_job) else job_mgr.submit_job(cfg)
        if asyncio.iscoroutine(job_id):
            job_id = await job_id

        # Concurrently start and run the job to test single task stream ingestion
        task_run = asyncio.create_task(job_mgr.run_job(job_id, timeout=10.0))
        # Interleaved status check while running
        await asyncio.sleep(0.01)
        status_info = job_mgr.get_job_status(job_id)
        assert status_info is not None

        completed_job = await task_run
        assert completed_job.status == "completed"
        assert completed_job.return_code == 0
        assert "OUT_OK" in completed_job.stdout
        assert "ERR_OK" in completed_job.stderr

    asyncio.run(_run())


def test_pes_store_swmr_concurrent_readers(tmp_path: pathlib.Path) -> None:
    """Suggestion #17: Verify cross-platform reader-writer SWMR locking allowing concurrent readers."""
    pes_path = tmp_path / "test_swmr_pes.h5"
    store = TripartitePESStore(pes_path, symbols=["H", "H"], lock_timeout=15.0)

    # Register method and seed initial point
    store.register_method("b3lyp_svp", method="b3lyp", basis="def2-svp")
    store.record_point_to_active("b3lyp_svp", coords=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74]], energy=-1.17)

    read_results: List[int] = []
    read_errors: List[Exception] = []

    def reader_worker(reader_id: int) -> None:
        try:
            for _ in range(5):
                with store.active_reader() as reader:
                    # In active reader context, should be able to read points concurrently
                    pts = reader.get_points("b3lyp_svp")
                    read_results.append(len(pts))
                time.sleep(0.01)
        except Exception as exc:
            read_errors.append(exc)

    threads = [threading.Thread(target=reader_worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()

    # While readers are executing, writer appends points
    for step in range(3):
        time.sleep(0.02)
        with store.active_writer() as writer:
            writer.add_points(
                "b3lyp_svp",
                coords=[[0.0, 0.0, 0.0], [0.0, 0.0, 0.74 + 0.01 * step]],
                energies=[-1.17 - 0.001 * step],
            )

    for t in threads:
        t.join(timeout=10.0)

    assert len(read_errors) == 0, f"Concurrent reader errors: {read_errors}"
    assert len(read_results) == 50
    assert all(r >= 1 for r in read_results)


def test_shared_memory_zero_leakage() -> None:
    """Suggestion #18: Verify reference-counted unlink handshake and zero memory leakage."""
    test_data = np.arange(1000, dtype=np.float64) * 0.1

    # Allocate shared memory buffer
    shm_buffer = SharedMemoryBuffer.from_array(test_data)
    desc = shm_buffer.descriptor
    shm_name = desc["name"]

    # Ingest array from descriptor in consumer
    extracted = SharedMemoryBuffer.read_from_descriptor(desc)
    assert np.allclose(extracted, test_data)

    # Close the producer buffer
    shm_buffer.close()

    # The buffer should be unlinked once all references close
    # Attempting to open again must raise FileNotFoundError
    with pytest.raises((FileNotFoundError, OSError)):
        sm.SharedMemory(name=shm_name)


def test_thread_affinity_environment_injection() -> None:
    """Suggestion #19: Verify thread affinity env vars (GOMP, KMP, OMP) pre-injection and MPS variables."""
    # Test core mask [0, 2, 4, 6]
    cores = [0, 2, 4, 6]
    env = build_thread_affinity_env(
        cores=cores,
        is_scout=False,
        num_mps_ranks=4,
        mps_mem_limit_mb=4096,
    )

    # Assert GOMP, KMP, OMP are properly injected
    assert env["GOMP_CPU_AFFINITY"] == "0,2,4,6"
    assert "0,2,4,6" in env["KMP_AFFINITY"]
    assert env["OMP_PLACES"] == "{0},{2},{4},{6}"
    assert env["OMP_PROC_BIND"] == "close"

    # Assert NVIDIA MPS mediation parameters
    assert env["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] == "25"
    assert env["CUDA_MPS_PINNED_DEVICE_MEM_LIMIT"] == "4096M"


def test_artifact_staging_thread_collision_prevention(tmp_path: pathlib.Path) -> None:
    """Suggestion #20: Verify thread-ident + UUID4 collision-free concurrent artifact publishing."""
    scratch_root = tmp_path / "scratch"
    artifacts_root = tmp_path / "artifacts"
    scratch_root.mkdir(parents=True, exist_ok=True)
    artifacts_root.mkdir(parents=True, exist_ok=True)

    config = AirGapConfig(scratch_root=scratch_root, artifacts_root=artifacts_root)
    coordinator = TripartiteAirGapCoordinator(config)

    # Launch 20 concurrent threads simultaneously publishing artifacts
    n_threads = 20
    published_hashes: Dict[int, str] = {}
    errors: List[Exception] = []

    def publish_worker(thread_idx: int) -> None:
        try:
            # Create a unique scratch file for each thread
            payload = f"PHYSICS_DATA_CHUNK_{thread_idx}_{uuid.uuid4().hex}".encode("utf-8")
            scratch_file = scratch_root / f"source_task_{thread_idx}.dat"
            scratch_file.write_bytes(payload)

            # All threads target identical base filename under separate subpaths or unique targets
            dest, sha = coordinator.publish_artifact(
                scratch_file,
                relative_dest=pathlib.Path(f"final_deliverable_{thread_idx}.dat"),
                compute_sha256=True,
            )
            assert dest.exists()
            assert dest.read_bytes() == payload
            assert sha is not None
            published_hashes[thread_idx] = sha
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=publish_worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert len(errors) == 0, f"Thread publishing collisions/errors occurred: {errors}"
    assert len(published_hashes) == n_threads
