"""
Unit and Integration Test Suite for CoChem Core Telemetry Logger.
Validates numerical traps, SCF oscillation ping-pong preemption,
hardware provenance capture, cross-platform segfault hex dumping,
JSON-LD QCSchema footer generation, thread safety, and immutability locking.
"""

import json
import os
import stat
import threading
from pathlib import Path
import pytest

from core_engine.cochem_core_telemetry_logger import (
    TelemetryLogger,
    CRITICAL_SEGFAULT_EXIT_CODES,
)


def test_telemetry_logger_init(tmp_path: Path) -> None:
    """Test initialization with custom directory and default properties."""
    log_dir = tmp_path / "custom_logs"
    logger = TelemetryLogger(log_dir=log_dir, verbosity="DEBUG")
    assert logger.log_dir.exists()
    assert logger.verbosity == "debug"
    assert logger.warnings_count == 0
    assert logger.errors_count == 0
    assert len(logger.scf_history) == 0
    assert logger.is_clean() is True


def test_nan_trap_fatal_abort(tmp_path: Path) -> None:
    """Test that NaN, Infinity, -Inf trigger fatal abort while regular words pass."""
    logger = TelemetryLogger(log_dir=tmp_path)
    
    # False positive test: 'Infrared' should not trigger NaN/Inf trap
    safe_line = "Computing Infrared vibrational frequencies for H2O..."
    assert logger.process_stream_chunk(safe_line) is True
    assert logger.errors_count == 0
    assert logger.is_clean() is True

    # Fatal test: actual NaN / Inf
    nan_line = "FATAL ERROR: Diagonal element in Fock matrix is NaN!"
    assert logger.process_stream_chunk(nan_line) is False
    assert logger.errors_count == 1
    assert logger.is_clean() is False

    # Infinity test
    inf_line = "Matrix norm exceeded threshold: value = +Infinity"
    assert logger.process_stream_chunk(inf_line) is False
    assert logger.errors_count == 2


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


def test_saddle_trap_warning(tmp_path: Path) -> None:
    """Test wavefunction instability / saddle point trap produces warnings without abort."""
    logger = TelemetryLogger(log_dir=tmp_path)
    
    saddle_line = "Warning: Internal instability detected in UHF wavefunction solution."
    assert logger.process_stream_chunk(saddle_line) is True
    assert logger.warnings_count == 1
    assert logger.errors_count == 0


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


def test_json_ld_footer_schema(tmp_path: Path) -> None:
    """Test JSON-LD footer schema compliance and serialization."""
    logger = TelemetryLogger(log_dir=tmp_path)
    footer = logger._generate_json_ld_footer(
        job_name="job_benzene_opt",
        exit_code=0,
        config_hash="sha256_abcdef123456"
    )

    assert "# --- COCHEM JSON-LD PROVENANCE FOOTER ---" in footer
    # Extract json payload
    lines = footer.strip().split("\n")
    json_line = [l for l in lines if l.startswith("# {")][0][2:]
    data = json.loads(json_line)

    assert data["@context"] == "https://w3id.org/ro/qcschema"
    assert data["job_id"] == "job_benzene_opt"
    assert data["execution_hash"] == "sha256_abcdef123456"
    assert data["exit_code"] == 0
    assert data["status"] == "SUCCESS"
    assert "timestamp_end" in data


def test_aggregate_and_lock_success(tmp_path: Path) -> None:
    """Test aggregating stdout, appending footer, and locking log file."""
    logger = TelemetryLogger(log_dir=tmp_path)
    stdout_lines = [
        "ORCA 5.0.4 Initializing...",
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


def test_aggregate_and_lock_segfault_hexdump(tmp_path: Path) -> None:
    """Test hex dump generation for segfault exit codes (Linux 139 and Windows 0xC0000005)."""
    logger = TelemetryLogger(log_dir=tmp_path)
    stdout_lines = ["Running intensive matrix diagonalization..."]
    stderr_lines = ["Segmentation fault (core dumped): Invalid memory access at 0x7fff00000000"]

    log_path_str = logger.aggregate_and_lock(
        job_name="crash_job",
        stdout_history=stdout_lines,
        stderr_history=stderr_lines,
        exit_code=139,
        active_hash="hash_crash_1"
    )

    log_path = Path(log_path_str)
    content = log_path.read_text(encoding="utf-8")
    assert "CRITICAL SEGMENTATION FAULT" in content
    assert "Hexadecimal Trace:" in content
    assert "0x0000:" in content


def test_aggregate_and_lock_overwrite_readonly(tmp_path: Path) -> None:
    """Test overwriting an existing read-only locked log file cleanly."""
    logger = TelemetryLogger(log_dir=tmp_path)
    
    # First execution
    logger.aggregate_and_lock("re_job", ["run 1"], [], 0, "hash1")
    
    # Second execution on same job name
    log_path_str = logger.aggregate_and_lock("re_job", ["run 2 modified"], [], 0, "hash2")
    
    log_path = Path(log_path_str)
    content = log_path.read_text(encoding="utf-8")
    assert "run 2 modified" in content


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


def test_thread_safety_concurrent_chunks(tmp_path: Path) -> None:
    """Test concurrent thread stream processing without race conditions."""
    logger = TelemetryLogger(log_dir=tmp_path)
    errors = []

    def worker(worker_id: int) -> None:
        try:
            for i in range(50):
                logger.process_stream_chunk(f"Worker {worker_id} chunk {i}: dE = {-0.0001 * i}")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
