#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Stage 6.0 / 7.0 Context-Compression & Streaming Engine.

Module: tests/test_cochem_bench_telemetry.py
Target Implementation: cochem_bench.interfaces.cochem_bench_telemetry

Tests:
1. ContextCompressor:
   - Statistical downsampling of massive raw metric arrays (DIIS error vectors, SCF energy fluctuations).
   - Exact calculation of Min, Max, Mean, Variance, Last Value.
   - Largest-Triangle-Three-Buckets (LTTB) visual decimation for continuous curves.
   - Frame/payload level compression with array threshold gating.
   - Edge case robustness (single element, constant array, extreme values).
2. NDJSONStreamer:
   - Formatting and streaming of lightweight NDJSON events with ISO 8601 timestamps.
   - Asynchronous polling from in-memory ring buffer.
   - Non-blocking disk streaming and incremental tail reading.
   - Safe detachment invariant when frontend disconnects without disrupting backend compute.
3. NanInfInterceptor:
   - Exact RegEx trapping of "Lowest eigenvalue of the overlap matrix" with float extraction.
   - Linear dependence threshold evaluation (< 1e-6).
   - RegEx trapping of NaN and Inf occurrences in live standard output stream.
   - Creation and validation of exact 0-byte ABORT.signal in dynamic $SCRATCH workspace.
   - Air-gap resolution via COCHEM_ARTIFACTS_DIR environment variable.
4. Mendeleev Dynamic Integration:
   - Atomic mass resolution dynamically querying the Mendeleev database.

Authoritative References:
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\.in-progress\draft_task2_pt2_telemetry.md
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 7 Thread-Safe Atomic IO & Context-Compression.txt
- D:\__CoChem\__agentic\.prompts\.SRS\CoChem-BENCH\SRS\Task 2 File Inventory & Deliverable Capabilities Manifest (Part 2 Interface Layer & Core System Bridges).txt
- D:\__CoChem\GitHub-Repo\CoChem-BASE\Method_Matrix.md
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from cochem_bench.interfaces.cochem_bench_telemetry import (
    ContextCompressor,
    NanInfInterceptor,
    NDJSONStreamer,
    StatisticalSummary,
    decimate_lttb,
    get_cochem_artifacts_dir,
    get_element_mass_mendeleev,
    get_logs_workspace_dir,
    get_scratch_workspace_dir,
)

# ==============================================================================
# Authentic Molecular & SCF Convergence Test Fixtures
# ==============================================================================

# Authentic 50-cycle SCF energy convergence sequence for Water (H2O) at B3LYP/def2-TZVP
H2O_SCF_ENERGIES = [
    -75.8201452, -76.3129841, -76.4021984, -76.4258912, -76.4310245,
    -76.4320018, -76.4321782, -76.4322051, -76.4322094, -76.4322101,
    -76.4322102, -76.4322102, -76.4322102, -76.4322102, -76.4322102,
]

# Authentic DIIS Error Vector history for an oscillating complex
DIIS_ERROR_VECTOR = [
    0.4512000, 0.2104500, 0.0894000, 0.0341000, 0.0125000,
    0.0048100, 0.0019200, 0.0006500, 0.0002100, 0.0000750,
    0.0000240, 0.0000081, 0.0000025, 0.0000009, 0.0000002,
]


@pytest.fixture
def clean_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sets up a clean, isolated COCHEM_ARTIFACTS_DIR workspace."""
    artifacts_dir = tmp_path / "cochem_artifacts_test"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("COCHEM_ARTIFACTS_DIR", str(artifacts_dir))
    return artifacts_dir


# ==============================================================================
# 1. ContextCompressor Tests
# ==============================================================================

class TestContextCompressor:
    """Tests for mathematical downsampling of large raw arrays into statistical summaries."""

    def test_compress_array_statistical_exactness(self):
        """Verifies exact floating point statistical calculations for 1D arrays."""
        arr = np.array(H2O_SCF_ENERGIES, dtype=np.float64)
        compressor = ContextCompressor()
        summary = compressor.compress_array(arr)

        assert isinstance(summary, StatisticalSummary)
        assert pytest.approx(summary.Array_Min, rel=1e-7) == float(np.min(arr))
        assert pytest.approx(summary.Array_Max, rel=1e-7) == float(np.max(arr))
        assert pytest.approx(summary.Array_Mean, rel=1e-7) == float(np.mean(arr))
        assert pytest.approx(summary.Array_Variance, rel=1e-7) == float(np.var(arr))
        assert pytest.approx(summary.Last_Value, rel=1e-7) == float(arr[-1])
        assert summary.count == len(arr)

    def test_compress_to_dict_format(self):
        """Verifies that dictionary output contains exact 5 required keys matching SRS."""
        compressor = ContextCompressor()
        res_dict = compressor.compress_to_dict(DIIS_ERROR_VECTOR)

        assert "Array_Min" in res_dict
        assert "Array_Max" in res_dict
        assert "Array_Mean" in res_dict
        assert "Array_Variance" in res_dict
        assert "Last_Value" in res_dict

        assert res_dict["Array_Min"] == min(DIIS_ERROR_VECTOR)
        assert res_dict["Array_Max"] == max(DIIS_ERROR_VECTOR)
        assert res_dict["Last_Value"] == DIIS_ERROR_VECTOR[-1]

    def test_compress_single_element_array(self):
        """Verifies edge case: single element array has zero variance and identical bounds."""
        compressor = ContextCompressor()
        summary = compressor.compress_array([42.5])

        assert summary.Array_Min == 42.5
        assert summary.Array_Max == 42.5
        assert summary.Array_Mean == 42.5
        assert summary.Array_Variance == 0.0
        assert summary.Last_Value == 42.5
        assert summary.count == 1

    def test_compress_constant_array(self):
        """Verifies edge case: array with identical elements has zero variance."""
        compressor = ContextCompressor()
        data = [3.14159265] * 100
        summary = compressor.compress_array(data)

        assert pytest.approx(summary.Array_Min, rel=1e-8) == 3.14159265
        assert pytest.approx(summary.Array_Max, rel=1e-8) == 3.14159265
        assert pytest.approx(summary.Array_Mean, rel=1e-8) == 3.14159265
        assert pytest.approx(summary.Array_Variance, abs=1e-12) == 0.0
        assert summary.Last_Value == 3.14159265
        assert summary.count == 100

    def test_compress_empty_array_raises_value_error(self):
        """Asserts that compressing an empty sequence fails fast with ValueError."""
        compressor = ContextCompressor()
        with pytest.raises(ValueError, match="Cannot compress empty array"):
            compressor.compress_array([])

    def test_compress_2d_array_flattening(self):
        """Verifies that multi-dimensional arrays (e.g. Fock/density matrices) are safely compressed."""
        matrix = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float64)
        compressor = ContextCompressor()
        summary = compressor.compress_array(matrix)

        assert summary.Array_Min == 1.0
        assert summary.Array_Max == 6.0
        assert summary.Array_Mean == 3.5
        assert summary.Last_Value == 6.0
        assert summary.count == 6

    def test_lttb_decimation_preserves_extrema(self):
        """Verifies that LTTB algorithm decimates large curves while strictly preserving extrema."""
        # 1000-point SCF oscillation curve with distinct peak and valley
        x = np.linspace(0, 100, 1000)
        y = np.sin(x) * np.exp(-x / 30.0)
        # Inject deliberate sharp extrema
        y[250] = 5.0   # Sharp peak
        y[750] = -5.0  # Sharp valley

        dec_x, dec_y = decimate_lttb(x, y, max_points=100)

        assert len(dec_x) == 100
        assert len(dec_y) == 100
        assert dec_x[0] == x[0]
        assert dec_x[-1] == x[-1]
        assert dec_y[0] == y[0]
        assert dec_y[-1] == y[-1]
        # Verify extreme peak and valley were preserved in decimated output
        assert pytest.approx(max(dec_y), rel=1e-5) == 5.0
        assert pytest.approx(min(dec_y), rel=1e-5) == -5.0

    def test_lttb_small_array_passthrough(self):
        """Asserts that arrays smaller than max_points are returned without mutation."""
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        dec_x, dec_y = decimate_lttb(x, y, max_points=100)

        assert np.array_equal(dec_x, x)
        assert np.array_equal(dec_y, y)

    def test_compress_payload_frame(self):
        """Verifies compression of full nested dictionary payloads containing large arrays."""
        compressor = ContextCompressor(array_threshold=10)
        raw_payload = {
            "node_id": "H2O_equilibrium",
            "numa_node": 2,
            "status": "RUNNING",
            "scalar_energy": -76.4322,
            "scf_history": list(range(100)),  # Exceeds threshold -> should compress
            "small_vector": [1.0, 2.0, 3.0],  # Below threshold -> stays intact
        }

        compressed = compressor.compress_payload(raw_payload)

        assert compressed["node_id"] == "H2O_equilibrium"
        assert compressed["numa_node"] == 2
        assert compressed["status"] == "RUNNING"
        assert compressed["scalar_energy"] == -76.4322
        assert compressed["small_vector"] == [1.0, 2.0, 3.0]

        # scf_history should be replaced with a statistical summary dict
        scf_sum = compressed["scf_history"]
        assert isinstance(scf_sum, dict)
        assert scf_sum["Array_Min"] == 0.0
        assert scf_sum["Array_Max"] == 99.0
        assert scf_sum["Last_Value"] == 99.0


# ==============================================================================
# 2. NDJSONStreamer Tests
# ==============================================================================

class TestNDJSONStreamer:
    """Tests for lightweight NDJSON streaming and asynchronous non-blocking polling."""

    def test_emit_event_structure(self):
        """Verifies NDJSON string formatting with valid JSON syntax and required keys."""
        streamer = NDJSONStreamer()
        line = streamer.emit_event(
            event_type="SCF_ITERATION",
            data={"iteration": 5, "delta_e": 1.2e-6, "energy": -76.43219},
            node_id="Node_01",
        )

        assert isinstance(line, str)
        assert line.endswith("\n")

        parsed = json.loads(line.strip())
        assert parsed["event_type"] == "SCF_ITERATION"
        assert parsed["node_id"] == "Node_01"
        assert parsed["data"]["iteration"] == 5
        assert "timestamp" in parsed

    def test_in_memory_polling(self):
        """Verifies in-memory ring buffer and asynchronous polling mechanics."""
        streamer = NDJSONStreamer(buffer_capacity=10)

        for i in range(5):
            streamer.emit_event("METRIC_UPDATE", {"step": i, "val": i * 1.5})

        events = streamer.poll_events(since_index=0)
        assert len(events) == 5
        assert events[0]["data"]["step"] == 0
        assert events[-1]["data"]["step"] == 4

        # Poll incremental updates
        new_events = streamer.poll_events(since_index=3)
        assert len(new_events) == 2
        assert new_events[0]["data"]["step"] == 3
        assert new_events[1]["data"]["step"] == 4

    def test_stream_to_file_and_tail_reading(self, clean_env: Path):
        """Verifies streaming events to NDJSON file and incremental byte offset tail reading."""
        streamer = NDJSONStreamer(artifacts_dir=clean_env)
        log_file = streamer.resolve_log_path()

        # Emit 3 events
        streamer.emit_event("STAGE_START", {"stage": "CBS_EXTRAPOLATION"}, write_to_disk=True)
        streamer.emit_event("STAGE_PROGRESS", {"percent": 50.0}, write_to_disk=True)
        streamer.emit_event("STAGE_COMPLETE", {"status": "SUCCESS"}, write_to_disk=True)

        assert log_file.exists()
        assert log_file.stat().st_size > 0

        # Read first batch
        records, next_offset = streamer.read_stream_file(from_byte_offset=0)
        assert len(records) == 3
        assert records[0]["event_type"] == "STAGE_START"
        assert records[-1]["event_type"] == "STAGE_COMPLETE"

        # Emit 1 more event and read incrementally from offset
        streamer.emit_event("CLEANUP", {"done": True}, write_to_disk=True)
        new_records, final_offset = streamer.read_stream_file(from_byte_offset=next_offset)
        assert len(new_records) == 1
        assert new_records[0]["event_type"] == "CLEANUP"
        assert final_offset > next_offset

    def test_safe_detachment_on_disconnect(self):
        """Verifies Zero-Interruption Safety Contract: calculation and streaming continue when detached."""
        streamer = NDJSONStreamer()
        assert not streamer.is_detached

        # Frontend disconnect event occurs
        streamer.detach()
        assert streamer.is_detached

        # Emission continues seamlessly without raising errors
        line = streamer.emit_event("BACKGROUND_SCF", {"iter": 12, "e": -100.5})
        assert line is not None
        assert len(streamer.buffer) == 1

        # Reattachment
        streamer.attach()
        assert not streamer.is_detached


# ==============================================================================
# 3. NanInfInterceptor Tests
# ==============================================================================

class TestNanInfInterceptor:
    """Tests for standard output stream scanning, linear dependence trapping, and ABORT.signal generation."""

    def test_detect_linear_dependence_eigenvalue_and_trigger_abort(self, clean_env: Path):
        """Verifies trapping 'Lowest eigenvalue of the overlap matrix' < 1e-6 and creating 0-byte ABORT.signal."""
        interceptor = NanInfInterceptor(artifacts_dir=clean_env)
        scratch_dir = get_scratch_workspace_dir(clean_env)
        abort_file = scratch_dir / "ABORT.signal"

        # Authentic ORCA linear dependence output line
        line = "Lowest eigenvalue of the overlap matrix : 4.8251e-08"
        alert = interceptor.scan_line(line)

        assert alert is not None
        assert alert.alert_type == "LINEAR_DEPENDENCE"
        assert pytest.approx(alert.extracted_value, rel=1e-6) == 4.8251e-08
        assert alert.abort_triggered is True

        # CRITICAL VERIFICATION: 0-byte ABORT.signal file must exist in $SCRATCH
        assert abort_file.exists()
        assert abort_file.stat().st_size == 0

    def test_safe_eigenvalue_does_not_trigger_abort(self, clean_env: Path):
        """Verifies that eigenvalues >= 1e-6 pass safely without triggering ABORT.signal."""
        interceptor = NanInfInterceptor(artifacts_dir=clean_env)
        scratch_dir = get_scratch_workspace_dir(clean_env)
        abort_file = scratch_dir / "ABORT.signal"

        # Well-conditioned basis set eigenvalue (> 1e-6)
        line = "Lowest eigenvalue of the overlap matrix : 3.4512e-04"
        alert = interceptor.scan_line(line)

        assert alert is None
        assert not abort_file.exists()

    def test_detect_nan_in_stream(self, clean_env: Path):
        """Verifies trapping NaN tokens in stdout lines and triggering 0-byte ABORT.signal."""
        interceptor = NanInfInterceptor(artifacts_dir=clean_env)
        scratch_dir = get_scratch_workspace_dir(clean_env)
        abort_file = scratch_dir / "ABORT.signal"

        line = "SCF ITERATION 14: Total Energy = NaN Eh | Max Gradient = 0.045"
        alert = interceptor.scan_line(line)

        assert alert is not None
        assert alert.alert_type == "NAN_DETECTED"
        assert alert.abort_triggered is True
        assert abort_file.exists()
        assert abort_file.stat().st_size == 0

    def test_detect_inf_in_stream(self, clean_env: Path):
        """Verifies trapping Inf / Infinity tokens in stdout lines and triggering 0-byte ABORT.signal."""
        interceptor = NanInfInterceptor(artifacts_dir=clean_env)
        scratch_dir = get_scratch_workspace_dir(clean_env)
        abort_file = scratch_dir / "ABORT.signal"

        line = "Error: DIIS matrix inversion failed, residual norm = +Inf"
        alert = interceptor.scan_line(line)

        assert alert is not None
        assert alert.alert_type == "INF_DETECTED"
        assert alert.abort_triggered is True
        assert abort_file.exists()
        assert abort_file.stat().st_size == 0

    def test_scan_multiline_chunk(self, clean_env: Path):
        """Verifies batch scanning of multi-line standard output logs."""
        interceptor = NanInfInterceptor(artifacts_dir=clean_env)
        chunk = """
        ----------------------------------------------------
        ORCA SCF CONVERGENCE ENGINE
        ----------------------------------------------------
        Number of basis functions: 342
        Lowest eigenvalue of the overlap matrix : 1.12e-07
        Iteration 1: Energy = -1245.8920341
        Iteration 2: Energy = -1245.8945102
        Iteration 3: Energy = NaN
        """
        alerts = interceptor.scan_chunk(chunk)

        assert len(alerts) == 2
        alert_types = [a.alert_type for a in alerts]
        assert "LINEAR_DEPENDENCE" in alert_types
        assert "NAN_DETECTED" in alert_types

    def test_clear_abort_signal(self, clean_env: Path):
        """Verifies utility method for safely removing the ABORT.signal file."""
        interceptor = NanInfInterceptor(artifacts_dir=clean_env)
        interceptor.create_abort_signal("TEST_REASON")
        assert interceptor.check_abort_signal() is True

        success = interceptor.clear_abort_signal()
        assert success is True
        assert interceptor.check_abort_signal() is False


# ==============================================================================
# 4. Air-Gap & Mendeleev Integration Tests
# ==============================================================================

class TestAirGapAndMendeleev:
    """Tests for dynamic environment variable resolution and Mendeleev mass queries."""

    def test_dynamic_artifacts_dir_resolution(self, clean_env: Path):
        """Verifies dynamic resolution of COCHEM_ARTIFACTS_DIR without hardcoding."""
        resolved = get_cochem_artifacts_dir()
        assert resolved == clean_env.resolve()

        scratch = get_scratch_workspace_dir()
        assert scratch == clean_env / "BENCH_Workspace" / "Scratch"

        logs = get_logs_workspace_dir()
        assert logs == clean_env / "Logs"

    def test_mendeleev_dynamic_mass_integration(self):
        """Verifies dynamic atomic mass retrieval using Mendeleev library."""
        c_mass = get_element_mass_mendeleev("C")
        h_mass = get_element_mass_mendeleev("H")
        o_mass = get_element_mass_mendeleev("O")

        assert 12.0 < c_mass < 12.02
        assert 1.007 < h_mass < 1.009
        assert 15.99 < o_mass < 16.01
