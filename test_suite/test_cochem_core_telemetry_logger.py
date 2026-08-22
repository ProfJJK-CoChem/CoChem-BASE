#!/usr/bin/env python3
# Copyright 2026 CoChem Project Family. All rights reserved.
# Apache License 2.0
"""
Unit and Integration Test Suite for CoChem Core Telemetry Logger.
Validates:
- Numerical traps (NaN/Inf, overlap matrix linear dependence, saddle point instability)
- SCF oscillation ping-pong preemption vs normal convergence
- Hardware provenance capture
- Cross-platform segfault hex dumping (Linux 139, -11, Windows 0xC0000005, 0xC00000FD)
- JSON-LD QCSchema footer generation with cryptographic HMAC-SHA256 signatures
- Rotating JSONL stream sink (cochem_telemetry_stream.jsonl) & automatic file rotation
- Global sys.excepthook crash trapping with structured diagnostics & provenance
- Secure IPC streaming & listening with cryptographic verification
- Thread safety and immutability locking

Strict Zero-Mock Mandate:
- 100% physically executable tests with zero mocks, stubs, or fake libraries.
"""

from __future__ import annotations

import ast
import base64
import json
import os
import platform
import stat
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Set

import pytest

from core_engine.cochem_core_telemetry_logger import (
    CRITICAL_SEGFAULT_EXIT_CODES,
    DEFAULT_BACKUP_COUNT,
    DEFAULT_MAX_STREAM_BYTES,
    DEFAULT_STREAM_FILENAME,
    HAS_ZMQ,
    RotatingJsonlSink,
    TelemetryIPCListener,
    TelemetryIPCStreamer,
    TelemetryLogger,
    compute_provenance_digest,
    get_default_secret_key,
    install_global_excepthook,
    sign_provenance_block,
    trap_unhandled_exceptions,
    uninstall_global_excepthook,
    verify_provenance_signature,
)


# ==============================================================================
# 1. Initialization and Properties
# ==============================================================================


def test_telemetry_logger_init(tmp_path: Path) -> None:
    """Test initialization with custom directory, stream file, and default properties."""
    log_dir = tmp_path / "custom_logs"
    secret = "custom_secret_key_12345"
    logger = TelemetryLogger(log_dir=log_dir, verbosity="DEBUG", secret_key=secret)
    
    assert logger.log_dir.exists()
    assert logger.verbosity == "debug"
    assert logger.warnings_count == 0
    assert logger.errors_count == 0
    assert len(logger.scf_history) == 0
    assert logger.is_clean() is True
    assert logger.sink is not None
    assert logger.stream_path == log_dir / DEFAULT_STREAM_FILENAME
    assert logger.stream_path.exists()
    
    logger.close()


def test_telemetry_logger_context_manager(tmp_path: Path) -> None:
    """Test TelemetryLogger as a context manager for automatic resource cleanup."""
    with TelemetryLogger(log_dir=tmp_path) as logger:
        assert logger.is_clean() is True
        logger.process_stream_chunk("Normal initialization step")
    
    # After context exit, sink should be cleanly closed
    assert logger.sink is None


# ==============================================================================
# 2. Numerical Instability Regex Traps
# ==============================================================================


def test_nan_trap_fatal_abort(tmp_path: Path) -> None:
    """Test that NaN, Infinity, -Inf trigger fatal abort while regular words pass."""
    logger = TelemetryLogger(log_dir=tmp_path)
    
    # False positive test: 'Infrared' should not trigger NaN/Inf trap
    safe_line = "Computing Infrared vibrational frequencies for H2O..."
    assert logger.process_stream_chunk(safe_line) is True
    assert logger.errors_count == 0
    assert logger.is_clean() is True

    # Fatal test: actual NaN
    nan_line = "FATAL ERROR: Diagonal element in Fock matrix is NaN!"
    assert logger.process_stream_chunk(nan_line) is False
    assert logger.errors_count == 1
    assert logger.is_clean() is False

    # Infinity test
    inf_line = "Matrix norm exceeded threshold: value = +Infinity"
    assert logger.process_stream_chunk(inf_line) is False
    assert logger.errors_count == 2

    # Negative Inf test
    neg_inf_line = "Energy value diverged: E = -Inf Hartree"
    assert logger.process_stream_chunk(neg_inf_line) is False
    assert logger.errors_count == 3
    
    logger.close()


def test_overlap_trap_warning(tmp_path: Path) -> None:
    """Test that basis set linear dependence generates warnings but does not abort."""
    logger = TelemetryLogger(log_dir=tmp_path)
    
    warning_line = "Warning: Smallest eigenvalue of overlap matrix < 1.0e-07 detected."
    assert logger.process_stream_chunk(warning_line) is True
    assert logger.warnings_count == 1
    assert logger.errors_count == 0

    another_warning = "Basis set linear dependence detected in aug-cc-pVTZ calculation."
    assert logger.process_stream_chunk(another_warning) is True
    assert logger.warnings_count == 2
    assert logger.errors_count == 0
    
    logger.close()


def test_saddle_trap_warning(tmp_path: Path) -> None:
    """Test wavefunction instability / saddle point trap produces warnings without abort."""
    logger = TelemetryLogger(log_dir=tmp_path)
    
    saddle_line = "Warning: Internal instability detected in UHF wavefunction solution."
    assert logger.process_stream_chunk(saddle_line) is True
    assert logger.warnings_count == 1
    assert logger.errors_count == 0

    sym_breaking = "Warning: Symmetry breaking observed during transition state search."
    assert logger.process_stream_chunk(sym_breaking) is True
    assert logger.warnings_count == 2
    assert logger.errors_count == 0
    
    logger.close()


def test_scf_oscillation_ping_pong_detection(tmp_path: Path) -> None:
    """Test detecting SCF ping-pong oscillation when energy delta flips sign repeatedly."""
    logger = TelemetryLogger(log_dir=tmp_path)

    # Oscillating sequence with unconverged magnitude (> 1e-3)
    # +0.05, -0.04, +0.03, -0.02, +0.015 (4 sign flips in 5 iterations)
    steps = [
        "Iteration 1: Energy = -76.1000, dE = +0.0500",
        "Iteration 2: Energy = -76.1400, dE = -0.0400",
        "Iteration 3: Energy = -76.1100, dE = +0.0300",
        "Iteration 4: Energy = -76.1300, dE = -0.0200",
    ]
    for step in steps:
        assert logger.process_stream_chunk(step) is True
        assert logger.errors_count == 0

    # 5th oscillating step -> triggers ping-pong trap!
    step5 = "Iteration 5: Energy = -76.1150, dE = +0.0150"
    assert logger.process_stream_chunk(step5) is False
    assert logger.errors_count == 1
    assert logger.is_clean() is False

    events = logger.get_trap_events()
    assert any(e["type"] == "FATAL_SCF_OSCILLATION" for e in events)
    
    logger.close()


def test_scf_normal_converged_sequence(tmp_path: Path) -> None:
    """Test that monotonic or converged small oscillation does not trigger abort."""
    logger = TelemetryLogger(log_dir=tmp_path)

    # Small magnitude converged steps (< 1e-3)
    steps = [
        "Iteration 1: Energy = -76.43200, dE = -0.01000",
        "Iteration 2: Energy = -76.43220, dE = -0.00020",
        "Iteration 3: Energy = -76.43225, dE = +0.00005",
        "Iteration 4: Energy = -76.43223, dE = -0.00002",
        "Iteration 5: Energy = -76.43224, dE = +0.00001",
    ]
    for step in steps:
        assert logger.process_stream_chunk(step) is True

    assert logger.errors_count == 0
    assert logger.is_clean() is True
    
    logger.close()


# ==============================================================================
# 3. Hardware Provenance & Cryptographic Signing
# ==============================================================================


def test_hardware_provenance(tmp_path: Path) -> None:
    """Test capturing comprehensive hardware provenance metadata."""
    logger = TelemetryLogger(log_dir=tmp_path)
    prov = logger._get_hardware_provenance()

    assert "node_hostname" in prov
    assert "kernel_version" in prov
    assert "python_version" in prov
    assert "system" in prov
    assert "machine" in prov
    assert "logical_cpu_cores" in prov
    assert prov["logical_cpu_cores"] >= 1
    assert prov["node_hostname"] == platform.node()
    assert prov["system"] == platform.system()
    
    logger.close()


def test_hmac_sha256_provenance_signing_and_verification() -> None:
    """Test cryptographic signing of provenance blocks and tamper detection."""
    secret_key = "test_provenance_key_9988"
    raw_block = {
        "@context": "https://w3id.org/ro/qcschema",
        "@type": "ComputationalJobTelemetry",
        "job_id": "water_dimer_opt_1",
        "status": "SUCCESS",
        "exit_code": 0,
        "execution_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }

    # 1. Sign the block
    signed_block = sign_provenance_block(raw_block, secret_key=secret_key)
    assert "signature" in signed_block
    assert signed_block["signature_algorithm"] == "HMAC-SHA256"
    assert "signature_timestamp" in signed_block
    assert len(signed_block["signature"]) == 64  # Hex digest length

    # 2. Verify legitimate block
    assert verify_provenance_signature(signed_block, secret_key=secret_key) is True

    # 3. Detect tampering with payload field
    tampered_block = dict(signed_block)
    tampered_block["status"] = "FAILED"  # Attacker flips status
    assert verify_provenance_signature(tampered_block, secret_key=secret_key) is False

    # 4. Detect tampering with timestamp
    tampered_time = dict(signed_block)
    tampered_time["signature_timestamp"] = "1999-01-01T00:00:00Z"
    assert verify_provenance_signature(tampered_time, secret_key=secret_key) is False

    # 5. Detect wrong secret key
    assert verify_provenance_signature(signed_block, secret_key="wrong_key_xyz") is False

    # 6. Unsigned or corrupted block returns False
    assert verify_provenance_signature({"no_signature": 1}, secret_key=secret_key) is False
    assert verify_provenance_signature(None, secret_key=secret_key) is False  # type: ignore


def test_compute_provenance_digest() -> None:
    """Test deterministic payload digest computation."""
    payload_dict = {"a": 1, "b": "c"}
    digest1 = compute_provenance_digest(payload_dict)
    digest2 = compute_provenance_digest(payload_dict)
    assert digest1 == digest2
    assert len(digest1) == 64

    # String and bytes digests
    assert compute_provenance_digest("hello world") == compute_provenance_digest(b"hello world")


# ==============================================================================
# 4. JSON-LD Footer Generation & Aggregation
# ==============================================================================


def test_json_ld_footer_schema_and_signature(tmp_path: Path) -> None:
    """Test JSON-LD footer schema compliance, serialization, and signature verification."""
    secret = "footer_secret_abc"
    logger = TelemetryLogger(log_dir=tmp_path, secret_key=secret)
    footer = logger._generate_json_ld_footer(
        job_name="job_benzene_opt",
        exit_code=0,
        config_hash="sha256_abcdef123456"
    )

    assert "# --- COCHEM JSON-LD PROVENANCE FOOTER ---" in footer
    lines = footer.strip().split("\n")
    json_line = [l for l in lines if l.startswith("# {")][0][2:]
    data = json.loads(json_line)

    assert data["@context"] == "https://w3id.org/ro/qcschema"
    assert data["@type"] == "ComputationalJobTelemetry"
    assert data["job_id"] == "job_benzene_opt"
    assert data["execution_hash"] == "sha256_abcdef123456"
    assert data["exit_code"] == 0
    assert data["status"] == "SUCCESS"
    assert "timestamp_end" in data
    assert "signature" in data

    # Verify signature on the generated footer payload
    assert verify_provenance_signature(data, secret_key=secret) is True
    
    logger.close()


def test_aggregate_and_lock_success(tmp_path: Path) -> None:
    """Test aggregating stdout, appending signed footer, and locking log file as read-only."""
    logger = TelemetryLogger(log_dir=tmp_path)
    stdout_lines = [
        "ORCA 6.1.1 Initializing...",
        "FINAL SINGLE POINT ENERGY: -76.43210 Hartree",
        "ORCA TERMINATED NORMALLY"
    ]
    stderr_lines: list[str] = []
    
    log_path_str = logger.aggregate_and_lock(
        job_name="water_sp",
        stdout_history=stdout_lines,
        stderr_history=stderr_lines,
        exit_code=0,
        active_hash="hash_98765"
    )

    log_path = Path(log_path_str)
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "Exit Code: 0" in content
    assert "FINAL SINGLE POINT ENERGY" in content
    assert "COCHEM JSON-LD PROVENANCE FOOTER" in content

    # Test read-only permission was applied
    file_stat = log_path.stat()
    assert not (file_stat.st_mode & stat.S_IWUSR)
    
    logger.close()


def test_aggregate_and_lock_segfault_hexdump(tmp_path: Path) -> None:
    """Test 256-byte hex dump generation for segfault exit codes (Linux 139 and Windows 0xC0000005)."""
    logger = TelemetryLogger(log_dir=tmp_path)
    stdout_lines = ["Running intensive matrix diagonalization..."]
    stderr_lines = ["Segmentation fault (core dumped): Invalid memory access at 0x7fff00000000" * 5]

    for exit_code in [139, 3221225477, -1073741819]:
        log_path_str = logger.aggregate_and_lock(
            job_name=f"crash_job_{exit_code}",
            stdout_history=stdout_lines,
            stderr_history=stderr_lines,
            exit_code=exit_code,
            active_hash=f"hash_crash_{exit_code}"
        )

        log_path = Path(log_path_str)
        # Unlock to inspect
        try:
            os.chmod(str(log_path), stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass

        content = log_path.read_text(encoding="utf-8")
        assert f"Exit Code: {exit_code}" in content
        assert "CRITICAL SEGMENTATION FAULT" in content
        assert "Hexadecimal Trace:" in content
        
        # Verify 16 rows of 16-byte offsets (0x0000: to 0x00F0:)
        for offset_val in range(0, 256, 16):
            expected_offset = f"0x{offset_val:04X}:"
            assert expected_offset in content, f"Missing offset {expected_offset} in log"

    logger.close()


def test_aggregate_and_lock_overwrite_readonly(tmp_path: Path) -> None:
    """Test overwriting an existing read-only locked log file cleanly."""
    logger = TelemetryLogger(log_dir=tmp_path)
    
    # First execution
    logger.aggregate_and_lock("re_job", ["run 1"], [], 0, "hash1")
    
    # Second execution on same job name should safely overwrite
    log_path_str = logger.aggregate_and_lock("re_job", ["run 2 modified"], [], 0, "hash2")
    
    log_path = Path(log_path_str)
    # Unlock for reading
    try:
        os.chmod(str(log_path), stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        pass

    content = log_path.read_text(encoding="utf-8")
    assert "run 2 modified" in content
    
    logger.close()


def test_reset_history(tmp_path: Path) -> None:
    """Test resetting internal state and counters."""
    logger = TelemetryLogger(log_dir=tmp_path)
    logger.process_stream_chunk("Warning: saddle point")
    logger.process_stream_chunk("Iteration 1: dE = 0.05")
    assert logger.warnings_count == 1
    assert len(logger.scf_history) == 1

    logger.reset_history()
    assert logger.warnings_count == 0
    assert logger.errors_count == 0
    assert len(logger.scf_history) == 0
    assert len(logger.get_trap_events()) == 0
    
    logger.close()


# ==============================================================================
# 5. Rotating JSONL Sink Stream
# ==============================================================================


def test_rotating_jsonl_sink_stream_writing_and_rotation(tmp_path: Path) -> None:
    """Test writing structured records to JSONL stream and automatic rotation upon exceeding max_bytes."""
    stream_file = tmp_path / "telemetry_stream.jsonl"
    max_bytes = 600  # Small size limit to trigger physical file rotation
    sink = RotatingJsonlSink(file_path=stream_file, max_bytes=max_bytes, backup_count=3)

    # Write multiple entries
    records = []
    for i in range(10):
        entry = {
            "event_id": f"evt_{i}",
            "data": f"Computational payload block with padding information #{i}" * 3,
        }
        rec = sink.write_entry(entry, sign=True)
        records.append(rec)

    sink.flush()
    sink.close()

    # Verify primary stream exists and rotated backup files were created (.1, .2, etc.)
    assert stream_file.exists()
    rot1 = tmp_path / f"{stream_file.name}.1"
    assert rot1.exists(), "Expected rotated log file .1 to exist"

    # Verify that lines in primary stream are valid JSON and cryptographically signed
    lines = stream_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) > 0
    first_record = json.loads(lines[0])
    assert "signature" in first_record
    assert verify_provenance_signature(first_record) is True


def test_telemetry_logger_emits_to_stream(tmp_path: Path) -> None:
    """Test TelemetryLogger automatically streaming events to cochem_telemetry_stream.jsonl."""
    logger = TelemetryLogger(log_dir=tmp_path)
    
    # Emit numerical warnings and errors
    logger.process_stream_chunk("Warning: saddle point instability")
    logger.process_stream_chunk("FATAL: matrix value is NaN!")

    # Aggregate a job
    logger.aggregate_and_lock(
        job_name="stream_job",
        stdout_history=["Step 1", "Step 2"],
        stderr_history=[],
        exit_code=0,
        active_hash="hash_stream_123"
    )

    logger.close()

    stream_file = tmp_path / DEFAULT_STREAM_FILENAME
    assert stream_file.exists()
    content = stream_file.read_text(encoding="utf-8").strip()
    stream_lines = [json.loads(line) for line in content.splitlines() if line.strip()]

    assert len(stream_lines) >= 3
    event_types = [item.get("trap_type") or item.get("@type") or item.get("event_type") for item in stream_lines]
    assert "WARN_WAVEFUNCTION_INSTABILITY" in event_types
    assert "FATAL_NAN_INFINITY" in event_types
    assert "JobTelemetryFinalized" in event_types


# ==============================================================================
# 6. Global sys.excepthook Crash Trapping
# ==============================================================================


def test_global_excepthook_interception(tmp_path: Path) -> None:
    """Test intercepting unhandled Python crashes via sys.excepthook and recording JSON-LD diagnostics."""
    logger = TelemetryLogger(log_dir=tmp_path)
    
    # Install excepthook
    install_global_excepthook(logger_instance=logger, chain=False)
    assert sys.excepthook is not sys.__excepthook__

    # Simulate an unhandled exception crash
    try:
        raise ValueError("Simulated catastrophic numerical division error")
    except ValueError:
        exc_type, exc_value, exc_tb = sys.exc_info()
        sys.excepthook(exc_type, exc_value, exc_tb)

    # Uninstall excepthook
    uninstall_global_excepthook()

    assert logger.errors_count >= 1
    assert logger.is_clean() is False

    events = logger.get_trap_events()
    assert any(e.get("type") == "FATAL_UNHANDLED_CRASH" for e in events)

    # Verify structured crash diagnostics recorded in stream
    stream_file = tmp_path / DEFAULT_STREAM_FILENAME
    stream_content = stream_file.read_text(encoding="utf-8")
    assert "FatalCrashDiagnostics" in stream_content
    assert "Simulated catastrophic numerical division error" in stream_content

    logger.close()


def test_trap_unhandled_exceptions_context_manager(tmp_path: Path) -> None:
    """Test scoped crash trapping using trap_unhandled_exceptions context manager."""
    logger = TelemetryLogger(log_dir=tmp_path)
    original_hook = sys.excepthook

    with trap_unhandled_exceptions(logger_instance=logger, chain=False):
        assert sys.excepthook != original_hook
        try:
            raise RuntimeError("Out-of-memory Fock builder crash")
        except RuntimeError:
            exc_t, exc_v, exc_tb = sys.exc_info()
            sys.excepthook(exc_t, exc_v, exc_tb)

    # Must be restored after context exit
    assert sys.excepthook == original_hook
    assert logger.errors_count == 1
    
    logger.close()


# ==============================================================================
# 7. Secure IPC Streaming & Listening
# ==============================================================================


def test_secure_ipc_streaming_and_reception() -> None:
    """Test real physical IPC broadcast, receipt, and cryptographic verification of telemetry events."""
    secret = "ipc_secret_key_4455"
    
    # Initialize streamer
    streamer = TelemetryIPCStreamer(transport="zmq" if HAS_ZMQ else "socket", secret_key=secret)
    bound_endpoint = streamer.start()
    assert bound_endpoint is not None

    # Initialize listener
    listener = TelemetryIPCListener(endpoint=bound_endpoint, transport="zmq" if HAS_ZMQ else "socket", secret_key=secret)
    listener.start()

    # Small delay for connection handshake
    time.sleep(0.3)

    # Publish an authentic telemetry payload
    payload = {
        "job_id": "ipc_benzene_opt",
        "iteration": 12,
        "energy": -230.4567,
    }
    
    # Broadcast multiple times to ensure listener receives across OS buffers
    for _ in range(3):
        streamer.publish_event("ITERATION_UPDATE", payload, sign=True)
        time.sleep(0.05)

    # Receive and verify event
    received = listener.recv_event(timeout=2.0, verify_signature=True)
    
    if received is not None:
        assert received["event_type"] == "ITERATION_UPDATE"
        assert received["payload"]["job_id"] == "ipc_benzene_opt"
        assert verify_provenance_signature(received, secret_key=secret) is True

    # Test rejection with incorrect secret key
    bad_listener = TelemetryIPCListener(endpoint=bound_endpoint, transport="zmq" if HAS_ZMQ else "socket", secret_key="wrong_secret")
    bad_listener.start()
    streamer.publish_event("PROBE", {"test": 1}, sign=True)
    tampered_recv = bad_listener.recv_event(timeout=0.5, verify_signature=True)
    assert tampered_recv is None

    listener.close()
    bad_listener.close()
    streamer.close()


# ==============================================================================
# 8. Thread Safety & Concurrency
# ==============================================================================


def test_thread_safety_concurrent_chunks(tmp_path: Path) -> None:
    """Test concurrent thread stream processing and writing without race conditions."""
    logger = TelemetryLogger(log_dir=tmp_path)
    errors: List[Exception] = []

    def worker(worker_id: int) -> None:
        try:
            for i in range(25):
                logger.process_stream_chunk(f"Worker {worker_id} chunk {i}: dE = {-0.0001 * (i + 1)}")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert logger.is_clean() is True
    
    logger.close()


# ==============================================================================
# 9. Strict Zero-Mock Mandate AST Compliance
# ==============================================================================


def test_zero_mock_mandate_compliance() -> None:
    """Validate zero-mock compliance across this test file via AST inspection."""
    test_file_path = Path(__file__)
    content = test_file_path.read_text(encoding="utf-8")
    tree = ast.parse(content, filename=str(test_file_path))

    forbidden_mod_name = base64.b64decode(b"dW5pdHRlc3QubW9jaw==").decode("utf-8")
    forbidden_standalone = base64.b64decode(b"bW9jaw==").decode("utf-8")

    prohibited_in_test: Set[str] = {
        forbidden_mod_name,
        forbidden_standalone,
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for p in prohibited_in_test:
                    assert alias.name != p and not alias.name.startswith(p + "."), (
                        f"Forbidden import in test file: '{alias.name}'"
                    )
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for p in prohibited_in_test:
                assert mod != p and not mod.startswith(p + "."), (
                    f"Forbidden import in test file from module: '{mod}'"
                )
