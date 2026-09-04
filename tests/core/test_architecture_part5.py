"""Zero-Mock Architecture, IPC, Concurrency & Telemetry Test Suite (Part 5).

Validates Suggestions #41, #42, #44, and #45.
Adheres strictly to Method Matrix v4 and Zero-Mock Anti-Spoofing Protocol v2.
Real physical execution: authentic sockets, real threads, genuine HDF5 SWMR files.
"""

from __future__ import annotations

import atexit
import concurrent.futures
import json
import os
import pathlib
import socket
import tempfile
import threading
import time
from typing import List

import h5py
import numpy as np
import pytest

from cochem.core.cochem_sandbox import SandboxConfig, SandboxContext
from cochem.core.diagnostics.memory_guard import (
    MemoryGuard,
    MemoryTelemetrySample,
    discover_accelerator,
    dispatch_device_for_dtype,
)
from cochem.core.ipc.serializer import (
    HMACSocketClient,
    HMACSocketServer,
    IPCBindError,
    PortContentionError,
)


def test_hmac_socket_port_contention_recovery(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate dynamic loopback port contention recovery and atomic descriptor publishing (Suggestion #41)."""
    scratch_dir = tmp_path / "scratch_ipc"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(scratch_dir.resolve()))

    # 1. Bind a genuine holding socket to an ephemeral port to create guaranteed contention
    holding_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        try:
            holding_sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        except OSError:
            holding_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    else:
        holding_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    holding_sock.bind(("127.0.0.1", 0))
    holding_sock.listen(1)
    colliding_port = holding_sock.getsockname()[1]

    secret = b"authentic_super_secret_test_key_123"

    try:
        # 2. Instantiate server targeting the claimed colliding port
        server = HMACSocketServer(host="127.0.0.1", port=colliding_port, secret_key=secret)

        # 3. Assert port_fallback=False raises PortContentionError when port is busy
        with pytest.raises(PortContentionError):
            server.start(port_fallback=False, max_retries=2)

        # 4. Start with port_fallback=True (should dynamically re-bind to port 0)
        bound_port = server.start(port_fallback=True, max_retries=2)
        assert bound_port > 0
        assert bound_port != colliding_port
        assert server.port == bound_port

        # 5. Verify published descriptor file in COCHEM_SCRATCH_DIR
        pid = os.getpid()
        desc_file = scratch_dir / f"ipc_server_{pid}.json"
        assert desc_file.exists()

        desc_data = json.loads(desc_file.read_text(encoding="utf-8"))
        assert desc_data["pid"] == pid
        assert desc_data["host"] == "127.0.0.1"
        assert desc_data["port"] == bound_port
        assert "created_utc" in desc_data
        assert "auth_token_hash" in desc_data

        # 6. Transmit authentic payload from HMAC client
        client = HMACSocketClient(host="127.0.0.1", port=bound_port, secret_key=secret)
        test_payload = {"experiment": "conformer_scan", "coordinates": [0.0, 1.4, -0.5]}
        client.send_payload(test_payload)

        received = server.get_received_payload(timeout_sec=5.0)
        assert received == test_payload

        # 7. Teardown and verify atomic cleanup
        server.stop()
        assert not desc_file.exists()
    finally:
        holding_sock.close()


def test_sandbox_context_thread_safety_and_no_atexit_leak(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate that sandboxes in worker threads bypass signal traps and do not leak atexit handlers (Suggestion #42)."""
    scratch_dir = tmp_path / "sandbox_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(scratch_dir.resolve()))

    # 1. Background worker thread entering SandboxContext must NOT raise ValueError (signal only in main thread)
    worker_error: List[Exception] = []

    def background_worker() -> None:
        try:
            cfg = SandboxConfig()
            with SandboxContext(cfg) as sb:
                assert sb.root is not None
                assert sb.root.exists()
                # Verify scratch directory resolves under COCHEM_SCRATCH_DIR
                assert scratch_dir.resolve() in sb.root.resolve().parents
                test_file = sb.root / "work.dat"
                test_file.write_text("THREAD_WORK", encoding="utf-8")
        except Exception as exc:
            worker_error.append(exc)

    t = threading.Thread(target=background_worker)
    t.start()
    t.join(timeout=5.0)
    assert not worker_error, f"Background worker encountered signal error: {worker_error}"

    # 2. High-throughput sequential sandbox instantiation across thread pool must NOT accumulate atexit closures
    def _get_atexit_count() -> int:
        if hasattr(atexit, "_ncallbacks"):
            return atexit._ncallbacks()
        elif hasattr(atexit, "_exithandlers"):
            return len(atexit._exithandlers)
        return 0

    initial_atexit_count = _get_atexit_count()

    def pool_task(idx: int) -> int:
        with SandboxContext() as sb:
            assert sb.root is not None
            p = sb.root / f"task_{idx}.tmp"
            p.write_text(f"data_{idx}", encoding="utf-8")
            return idx

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(pool_task, i) for i in range(100)]
        results = [f.result(timeout=10.0) for f in futures]
        assert len(results) == 100

    # Constant number of atexit handlers proving zero unbounded closure leaks
    final_atexit_count = _get_atexit_count()
    assert final_atexit_count == initial_atexit_count, (
        f"atexit handlers leaked! initial={initial_atexit_count}, final={final_atexit_count}"
    )


def test_memory_guard_scf_plateau_detection() -> None:
    """Validate partitioned sub-window slope analysis and plateau leak suppression (Suggestion #44)."""
    # 1. Test SCF allocation plateau: 30 observations at 500 MB, sharp jump to 1500 MB, plateau at 1500 MB
    guard = MemoryGuard(window_capacity=60)
    base_time = 1000.0

    # First half (30 observations): steady 500 MB (500_000_000 bytes)
    for i in range(30):
        t = base_time + (i * 60.0)
        # Small realistic jitter (+/- 0.1 MB)
        jitter = ((i % 3) - 1) * 100_000
        guard.record_sample(
            MemoryTelemetrySample(timestamp_sec=t, rss_bytes=500_000_000 + jitter)
        )

    # Second half (30 observations): sharp step jump at obs 30 to 1500 MB, then bounded plateau
    for i in range(30, 60):
        t = base_time + (i * 60.0)
        noise = ((i % 5) - 2) * 200_000  # +/- 0.4 MB noise around plateau
        guard.record_sample(
            MemoryTelemetrySample(timestamp_sec=t, rss_bytes=1500_000_000 + noise)
        )

    is_leak, slope, r2 = guard.evaluate_leak()
    # Overall slope is large positive due to the step jump, but second half is plateaued (|slope_second| < 0.5)
    # The guard MUST classify this as a bounded step-function allocation and suppress the alert.
    assert is_leak is False, f"Expected plateau suppression, but got is_leak=True (slope={slope:.2f}, R2={r2:.4f})"

    # 2. Test genuine creeping leak: steady +10 MB per 60 seconds (10.0 MB/min) across entire window
    creeping_guard = MemoryGuard(window_capacity=60)
    leak_base_time = 5000.0
    for i in range(60):
        t = leak_base_time + (i * 60.0)
        rss = 200_000_000 + int(i * 10_000_000)  # +10 MB every 60s = 10 MB/min
        creeping_guard.record_sample(
            MemoryTelemetrySample(timestamp_sec=t, rss_bytes=rss)
        )

    leak_detected, leak_slope, leak_r2 = creeping_guard.evaluate_leak()
    assert leak_detected is True, "Creeping memory leak was not detected!"
    assert pytest.approx(leak_slope, rel=0.05) == 10.0
    assert leak_r2 > 0.95

    # 3. Test dynamic accelerator discovery & Apple Silicon MPS FP64 CPU fallback
    accel = discover_accelerator()
    assert "type" in accel
    assert "device" in accel
    assert "supports_fp64" in accel

    # If MPS device, verify FP64 compute routes to CPU
    dispatched = dispatch_device_for_dtype(dtype="float64", requested_device="mps")
    assert dispatched == "cpu"


def test_stage0_facade_and_swmr_hdf5_concurrency(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Validate stage-0 facade imports and Single-Writer-Multiple-Reader (SWMR) HDF5 concurrency (Suggestion #45)."""
    scratch_dir = tmp_path / "scratch_swmr"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_SCRATCH_DIR", str(scratch_dir.resolve()))

    # 1. Assert clean stage-0 facade imports
    from cochem_base.core import (
        CoChemHDF5Manager,
        MolecularTopology,
        PESPointRecord,
        PESStore,
        QCResultsRecord,
        RegistryManager,
        UnitConversionConstants,
    )
    assert CoChemHDF5Manager is not None
    assert RegistryManager is not None
    assert PESStore is not None
    assert QCResultsRecord is not None
    assert MolecularTopology is not None
    assert PESPointRecord is not None
    assert UnitConversionConstants is not None

    # 2. Initialize an HDF5 file via CoChemHDF5Manager with pre-allocated extensible dataset
    h5_file = tmp_path / "swmr_concurrency_test.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_file)

    initial_coords = np.array([[0.0, 1.4304, 1.1071]], dtype=np.float64)
    mgr.init_swmr_dataset(
        dataset_name="coordinates",
        initial_shape=(1, 3),
        maxshape=(None, 3),
        chunks=(32, 3),
        dtype=np.float64,
        initial_data=initial_coords,
    )

    # 3. 1 Writer thread writing 100 coordinate chunks and 3 Reader threads reading with dataset.refresh()
    num_cycles = 100
    errors: List[Exception] = []
    stop_readers = threading.Event()
    writer_ready = threading.Event()

    def writer_worker() -> None:
        try:
            with mgr.swmr_writer() as f:
                writer_ready.set()
                for idx in range(num_cycles):
                    chunk = np.full((1, 3), fill_value=float(idx + 1), dtype=np.float64)
                    mgr.append_swmr_chunk("coordinates", chunk, writer_file=f)
                    time.sleep(0.002)
                time.sleep(0.05)
                stop_readers.set()
        except Exception as exc:
            errors.append(exc)
        finally:
            writer_ready.set()
            stop_readers.set()

    def reader_worker(reader_id: int) -> None:
        try:
            if not writer_ready.wait(timeout=5.0):
                raise TimeoutError("Timed out waiting for SWMR writer initialization")
            with mgr.swmr_reader() as f:
                while not stop_readers.is_set():
                    data = mgr.read_swmr_dataset("coordinates", reader_file=f)
                    assert data.ndim == 2
                    assert data.shape[1] == 3
                    time.sleep(0.001)
        except Exception as exc:
            errors.append(exc)

    writer_t = threading.Thread(target=writer_worker, name="SWMRWriter")
    reader_threads = [
        threading.Thread(target=reader_worker, args=(r_id,), name=f"SWMRReader_{r_id}")
        for r_id in range(3)
    ]

    writer_t.start()
    for r in reader_threads:
        r.start()

    writer_t.join(timeout=15.0)
    stop_readers.set()
    for r in reader_threads:
        r.join(timeout=5.0)

    assert not errors, f"SWMR concurrency encountered errors: {errors}"

    # Verify final dataset size: 1 initial + 100 written = 101 entries
    final_data = mgr.read_swmr_dataset("coordinates")
    assert final_data.shape == (101, 3)
    assert final_data[-1, 0] == 100.0
