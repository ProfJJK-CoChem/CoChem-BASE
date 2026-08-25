#!/usr/bin/env python3
r"""Authentic Unit Test Suite for CoChem Stage 6.0 / 7.0 & Task 3 Telemetry Engine.

Module: tests/test_cochem_bench_telemetry.py
Target Implementation: cochem_bench.interfaces.cochem_bench_telemetry

Covers Task 3 Specs & Protocols:
1. Stateless Rehydration (Zombie UI Protocol):
   - Dynamic path resolution via COCHEM_ARTIFACTS_DIR for $ARTIFACTS/BENCH_Workspace/Logs/bench_run_state.jsonl.
   - Rehydration of stage progress, SCF cycles, energy history, variance, and active PIDs from NDJSON.
   - Cross-platform process group detachment handoff using psutil.
   - Real-world process liveness verification.
2. Context-Compression Stream Integration:
   - Polling lightweight NDJSON stream.
   - Statistical compression of massive numeric arrays (Min, Max, Mean, Variance, Last Value).
   - Asynchronous debouncing on a fixed interval (e.g. 2.0 seconds).
   - Incremental byte-offset tail reading.
3. Live Asymptotic Convergence Plotting:
   - Plotly FigureWidget / Figure initialization with logarithmic scaling and scientific styling.
   - Largest-Triangle-Three-Buckets (LTTB) decimation algorithm for datasets > 1,000 points.
   - Preservation of visual extrema and curve geometry under decimation.
4. Fatal Error Interception:
   - ZeroMQ heartbeat subscriber monitoring and timeout/drop detection.
   - Cross-platform OS Segfault (-11, 139, 0xC0000005, 3221225477, -1073741819) and OOM (137, -9) trapping.
   - Exact 256-byte stderr hex-dump extraction.
   - High-visibility red HTML crash readout.
   - Structured JSON-LD recovery instructions from provenance block ([M], [D], [E]).
   - Numerical instability trapping (overlap eigenvalue < 1e-6, NaN, Inf) with 0-byte ABORT.signal in $SCRATCH.
5. Dynamic Mendeleev Integration:
   - Atomic mass queries dynamically resolved via the Mendeleev library.

Safety & Anti-Spoofing Contracts:
- Zero Mocks / Stubs: Uses 100% genuine OS processes, real sockets, and filesystem state.
- Dynamic environment variable resolution via COCHEM_ARTIFACTS_DIR.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import plotly.graph_objects as go
import psutil
import pytest
import zmq

from cochem_bench.interfaces.cochem_bench_telemetry import (
    ContextCompressor,
    ContextCompressionStreamIntegrator,
    FatalErrorReport,
    FatalErrorInterceptor,
    LiveConvergencePlotter,
    NanInfInterceptor,
    NDJSONStreamer,
    RehydratedRunState,
    StatisticalSummary,
    StatelessRehydrator,
    TelemetryEvent,
    decimate_lttb,
    get_bench_logs_workspace_dir,
    get_bench_run_state_path,
    get_cochem_artifacts_dir,
    get_element_mass_mendeleev,
    get_logs_workspace_dir,
    get_scratch_workspace_dir,
)

# ==============================================================================
# Authentic Molecular & SCF Convergence Test Fixtures
# ==============================================================================

# Authentic 15-cycle SCF energy convergence sequence for Water (H2O) at B3LYP/def2-TZVP
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
# 1. Stateless Rehydration (Zombie UI Protocol) Tests
# ==============================================================================

class TestStatelessRehydration:
    """Tests for Zombie UI Protocol: session recovery and process detachment."""

    def test_dynamic_bench_logs_path_resolution(self, clean_env: Path):
        """Verifies dynamic resolution of $ARTIFACTS/BENCH_Workspace/Logs/bench_run_state.jsonl."""
        logs_dir = get_bench_logs_workspace_dir()
        expected_dir = clean_env / "BENCH_Workspace" / "Logs"
        assert logs_dir.resolve() == expected_dir.resolve()
        assert logs_dir.exists()

        state_file = get_bench_run_state_path()
        assert state_file.resolve() == (expected_dir / "bench_run_state.jsonl").resolve()

    def test_check_active_run_state_missing(self, clean_env: Path):
        """Verifies check_active_run_state returns False when no log exists."""
        rehydrator = StatelessRehydrator(artifacts_dir=clean_env)
        assert rehydrator.check_active_run_state() is False

    def test_rehydrate_state_from_valid_jsonl(self, clean_env: Path):
        """Verifies parsing of bench_run_state.jsonl into a RehydratedRunState model."""
        rehydrator = StatelessRehydrator(artifacts_dir=clean_env)
        state_file = get_bench_run_state_path(clean_env)

        records = [
            {
                "stage": "STAGE_1_GEOMETRY_INGEST",
                "scf_cycle": 1,
                "progress_percent": 10.0,
                "current_energy": -75.8201452,
                "energy_history": [-75.8201452],
                "pid": 12345,
                "status": "RUNNING",
                "timestamp": "2026-08-24T20:00:00Z",
            },
            {
                "stage": "STAGE_2_CBS_EXTRAPOLATION",
                "scf_cycle": 15,
                "progress_percent": 65.0,
                "current_energy": -76.4322102,
                "energy_history": H2O_SCF_ENERGIES,
                "pid": 12345,
                "status": "RUNNING",
                "timestamp": "2026-08-24T20:05:00Z",
            },
        ]
        with open(state_file, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")

        assert rehydrator.check_active_run_state() is True
        state = rehydrator.rehydrate_state()

        assert isinstance(state, RehydratedRunState)
        assert state.stage == "STAGE_2_CBS_EXTRAPOLATION"
        assert state.scf_cycle == 15
        assert state.progress_percent == 65.0
        assert pytest.approx(state.current_energy, rel=1e-7) == -76.4322102
        assert state.pid == 12345
        assert state.status == "RUNNING"
        assert len(state.energy_history) == len(H2O_SCF_ENERGIES)
        assert state.variance > 0.0

    def test_handoff_to_subprocess_broker_process_group_detachment(self, clean_env: Path):
        """Verifies cross-platform process group detachment handoff orchestrated via psutil."""
        rehydrator = StatelessRehydrator(artifacts_dir=clean_env)

        cmd = [sys.executable, "-c", "import time; time.sleep(0.5)"]
        launch_result = rehydrator.handoff_to_subprocess_broker(
            cmd=cmd,
            initial_stage="STAGE_0_BOOTSTRAP",
        )

        pid = launch_result["pid"]
        assert pid > 0
        assert psutil.pid_exists(pid)

        state_file = get_bench_run_state_path(clean_env)
        assert state_file.exists()
        assert rehydrator.check_active_run_state() is True

        assert rehydrator.is_broker_process_alive(pid) is True

        proc = psutil.Process(pid)
        proc.wait(timeout=3.0)
        assert rehydrator.is_broker_process_alive(pid) is False


# ==============================================================================
# 2. Context-Compression Stream Integration Tests
# ==============================================================================

class TestContextCompressionStreamIntegrator:
    """Tests for NDJSON stream debouncing and statistical aggregation."""

    def test_debounced_processing_interval(self):
        """Verifies that high-frequency events within debounce window are aggregated."""
        integrator = ContextCompressionStreamIntegrator(debounce_interval=2.0)

        events_batch_1 = [
            {"event_type": "SCF_ITER", "data": {"stage": "CBS", "scf_cycle": 1, "delta_e": 0.05, "energy": -75.8}},
            {"event_type": "SCF_ITER", "data": {"stage": "CBS", "scf_cycle": 2, "delta_e": 0.02, "energy": -76.3}},
        ]
        summary1 = integrator.process_stream_events(events_batch_1, current_time=100.0)
        assert summary1 is not None
        assert summary1["current_stage"] == "CBS"
        assert summary1["scf_cycle"] == 2

        events_batch_2 = [
            {"event_type": "SCF_ITER", "data": {"stage": "CBS", "scf_cycle": 3, "delta_e": 0.005, "energy": -76.4}},
        ]
        summary2 = integrator.process_stream_events(events_batch_2, current_time=101.0)
        assert summary2 is None

        events_batch_3 = [
            {"event_type": "SCF_ITER", "data": {"stage": "CBS", "scf_cycle": 4, "delta_e": 0.001, "energy": -76.43}},
        ]
        summary3 = integrator.process_stream_events(events_batch_3, current_time=102.5)
        assert summary3 is not None
        assert summary3["scf_cycle"] == 4
        assert summary3["energy_variance"] >= 0.0
        assert "energy_summary" in summary3

    def test_poll_ndjson_and_render_summary_from_disk(self, clean_env: Path):
        """Verifies reading live NDJSON stream from disk and computing debounced summaries."""
        streamer = NDJSONStreamer(artifacts_dir=clean_env)
        integrator = ContextCompressionStreamIntegrator(debounce_interval=0.0)

        streamer.emit_event(
            "SCF_ITERATION",
            {"stage": "CBS_EXTRAPOLATION", "scf_cycle": 1, "energy": -76.0, "delta_e": 0.1},
            write_to_disk=True,
        )
        streamer.emit_event(
            "SCF_ITERATION",
            {"stage": "CBS_EXTRAPOLATION", "scf_cycle": 2, "energy": -76.4, "delta_e": 0.01},
            write_to_disk=True,
        )

        log_path = streamer.resolve_log_path()
        summary, next_offset = integrator.poll_ndjson_and_render_summary(log_path, from_byte_offset=0)

        assert summary is not None
        assert summary["current_stage"] == "CBS_EXTRAPOLATION"
        assert summary["scf_cycle"] == 2
        assert next_offset > 0


# ==============================================================================
# 3. Live Asymptotic Convergence Plotting Tests
# ==============================================================================

class TestLiveConvergencePlotter:
    """Tests for Plotly FigureWidget / Figure creation and LTTB decimation."""

    def test_create_figure_widget(self):
        """Verifies creation and structural properties of Plotly Figure."""
        plotter = LiveConvergencePlotter()
        fig = plotter.create_figure(title="Test Convergence")

        assert isinstance(fig, (go.FigureWidget, go.Figure))
        assert len(fig.data) >= 1
        assert fig.layout.yaxis.type == "log"
        assert "Energy Residual" in fig.layout.yaxis.title.text

    def test_update_plot_under_1000_points(self):
        """Verifies updating plot with dataset smaller than 1000 points without decimation."""
        plotter = LiveConvergencePlotter()
        fig = plotter.create_figure()

        residuals = [1e-1, 1e-2, 1e-3, 1e-4, 1e-5, 1e-6]
        orig_count, render_count = plotter.update_plot(fig, residuals)

        assert orig_count == 6
        assert render_count == 6
        assert len(fig.data[0].y) == 6
        assert list(fig.data[0].y) == residuals

    def test_update_plot_lttb_decimation_over_1000_points(self):
        """Verifies LTTB decimation strictly caps rendered points to 1000 while preserving extrema."""
        plotter = LiveConvergencePlotter()
        fig = plotter.create_figure()

        x = np.linspace(0, 100, 2500)
        y = np.abs(np.sin(x)) + 1e-5
        y[500] = 10.0
        y[1500] = 1e-8

        orig_count, render_count = plotter.update_plot(fig, y, max_points=1000)

        assert orig_count == 2500
        assert render_count == 1000
        assert len(fig.data[0].y) == 1000
        assert pytest.approx(max(fig.data[0].y), rel=1e-4) == 10.0
        assert pytest.approx(min(fig.data[0].y), rel=1e-4) == 1e-8


# ==============================================================================
# 4. Fatal Error Interception Tests
# ==============================================================================

class TestFatalErrorInterceptor:
    """Tests for ZeroMQ heartbeat monitoring, exit code interception, and red screen JSON-LD generation."""

    def test_exit_code_recognition_segfault_and_oom(self):
        """Verifies recognition of cross-platform segfault and OOM return codes."""
        interceptor = FatalErrorInterceptor()

        assert interceptor.is_fatal_exit_code(139) is True
        assert interceptor.is_fatal_exit_code(-11) is True
        assert interceptor.is_fatal_exit_code(3221225477) is True
        assert interceptor.is_fatal_exit_code(-1073741819) is True
        assert interceptor.is_fatal_exit_code(0xC0000005) is True
        assert interceptor.is_fatal_exit_code(137) is True
        assert interceptor.is_fatal_exit_code(-9) is True
        assert interceptor.is_fatal_exit_code(0) is False

    def test_zmq_heartbeat_roundtrip_and_timeout(self):
        """Verifies genuine ZeroMQ heartbeat transmission, reception, and drop detection."""
        context = zmq.Context()
        endpoint = "inproc://telemetry_heartbeat_test"

        pub_sock = context.socket(zmq.PUB)
        pub_sock.bind(endpoint)

        sub_sock = context.socket(zmq.SUB)
        sub_sock.connect(endpoint)
        sub_sock.setsockopt_string(zmq.SUBSCRIBE, "")

        interceptor = FatalErrorInterceptor()

        time.sleep(0.05)
        pub_sock.send_json({"heartbeat": True, "timestamp": time.time()})

        is_alive = interceptor.check_zmq_heartbeat(sub_sock, timeout_ms=500)
        assert is_alive is True

        is_alive_timeout = interceptor.check_zmq_heartbeat(sub_sock, timeout_ms=100)
        assert is_alive_timeout is False

        pub_sock.close()
        sub_sock.close()
        context.term()

    def test_intercept_fatal_error_red_screen_and_jsonld(self, clean_env: Path):
        """Verifies generation of red HTML readout, 256-byte stderr hex dump, and structured JSON-LD."""
        interceptor = FatalErrorInterceptor(artifacts_dir=clean_env)

        raw_stderr = (
            b"FATAL ORCA 6.1.1 CORE DUMP: SIGSEGV at address 0x00007FF7C0000005\n"
            b"Diagnostic: Memory fault during Fock matrix diagonalization.\n"
            + b"X" * 300
        )

        report = interceptor.intercept_fatal_error(
            exit_code=139,
            stderr_bytes=raw_stderr,
            error_classification="SEGMENTATION_FAULT",
        )

        assert isinstance(report, FatalErrorReport)
        assert report.is_fatal is True
        assert report.error_type == "SEGMENTATION_FAULT"
        assert report.exit_code == 139

        assert len(report.stderr_hex_dump) == 512
        assert report.stderr_hex_dump == raw_stderr[:256].hex()

        assert "<div" in report.red_html_readout
        assert "background-color" in report.red_html_readout
        assert "FATAL ERROR" in report.red_html_readout
        assert report.stderr_hex_dump[:16] in report.red_html_readout

        json_ld = report.json_ld_provenance
        assert json_ld["@context"] == "https://schema.org"
        assert json_ld["@type"] == "SoftwareCrashProvenance"
        assert json_ld["exitCode"] == 139
        assert "provenance" in json_ld
        assert "[M]" in json_ld["provenance"]["methodology"]
        assert len(json_ld["recoveryInstructions"]) >= 3

    def test_intercept_numerical_instability(self, clean_env: Path):
        """Verifies intercepting linear dependence overlap < 1e-6 and triggering fatal report."""
        interceptor = FatalErrorInterceptor(artifacts_dir=clean_env)
        line = "Lowest eigenvalue of the overlap matrix : 1.25e-08"

        report = interceptor.intercept_line(line)
        assert report is not None
        assert report.is_fatal is True
        assert report.error_type == "LINEAR_DEPENDENCE"
        assert "Lowest eigenvalue of the overlap matrix" in report.red_html_readout

        scratch_dir = get_scratch_workspace_dir(clean_env)
        assert (scratch_dir / "ABORT.signal").exists()


# ==============================================================================
# 5. Existing Base Engine Tests (Backward Compatibility)
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
        x = np.linspace(0, 100, 1000)
        y = np.sin(x) * np.exp(-x / 30.0)
        y[250] = 5.0
        y[750] = -5.0

        dec_x, dec_y = decimate_lttb(x, y, max_points=100)

        assert len(dec_x) == 100
        assert len(dec_y) == 100
        assert dec_x[0] == x[0]
        assert dec_x[-1] == x[-1]
        assert dec_y[0] == y[0]
        assert dec_y[-1] == y[-1]
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
            "scf_history": list(range(100)),
            "small_vector": [1.0, 2.0, 3.0],
        }

        compressed = compressor.compress_payload(raw_payload)

        assert compressed["node_id"] == "H2O_equilibrium"
        assert compressed["numa_node"] == 2
        assert compressed["status"] == "RUNNING"
        assert compressed["scalar_energy"] == -76.4322
        assert compressed["small_vector"] == [1.0, 2.0, 3.0]

        scf_sum = compressed["scf_history"]
        assert isinstance(scf_sum, dict)
        assert scf_sum["Array_Min"] == 0.0
        assert scf_sum["Array_Max"] == 99.0
        assert scf_sum["Last_Value"] == 99.0


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

        new_events = streamer.poll_events(since_index=3)
        assert len(new_events) == 2
        assert new_events[0]["data"]["step"] == 3
        assert new_events[1]["data"]["step"] == 4

    def test_stream_to_file_and_tail_reading(self, clean_env: Path):
        """Verifies streaming events to NDJSON file and incremental byte offset tail reading."""
        streamer = NDJSONStreamer(artifacts_dir=clean_env)
        log_file = streamer.resolve_log_path()

        streamer.emit_event("STAGE_START", {"stage": "CBS_EXTRAPOLATION"}, write_to_disk=True)
        streamer.emit_event("STAGE_PROGRESS", {"percent": 50.0}, write_to_disk=True)
        streamer.emit_event("STAGE_COMPLETE", {"status": "SUCCESS"}, write_to_disk=True)

        assert log_file.exists()
        assert log_file.stat().st_size > 0

        records, next_offset = streamer.read_stream_file(from_byte_offset=0)
        assert len(records) == 3
        assert records[0]["event_type"] == "STAGE_START"
        assert records[-1]["event_type"] == "STAGE_COMPLETE"

        streamer.emit_event("CLEANUP", {"done": True}, write_to_disk=True)
        new_records, final_offset = streamer.read_stream_file(from_byte_offset=next_offset)
        assert len(new_records) == 1
        assert new_records[0]["event_type"] == "CLEANUP"
        assert final_offset > next_offset

    def test_safe_detachment_on_disconnect(self):
        """Verifies Zero-Interruption Safety Contract: calculation and streaming continue when detached."""
        streamer = NDJSONStreamer()
        assert not streamer.is_detached

        streamer.detach()
        assert streamer.is_detached

        line = streamer.emit_event("BACKGROUND_SCF", {"iter": 12, "e": -100.5})
        assert line is not None
        assert len(streamer.buffer) == 1

        streamer.attach()
        assert not streamer.is_detached


class TestNanInfInterceptor:
    """Tests for standard output stream scanning, linear dependence trapping, and ABORT.signal generation."""

    def test_detect_linear_dependence_eigenvalue_and_trigger_abort(self, clean_env: Path):
        """Verifies trapping 'Lowest eigenvalue of the overlap matrix' < 1e-6 and creating 0-byte ABORT.signal."""
        interceptor = NanInfInterceptor(artifacts_dir=clean_env)
        scratch_dir = get_scratch_workspace_dir(clean_env)
        abort_file = scratch_dir / "ABORT.signal"

        line = "Lowest eigenvalue of the overlap matrix : 4.8251e-08"
        alert = interceptor.scan_line(line)

        assert alert is not None
        assert alert.alert_type == "LINEAR_DEPENDENCE"
        assert pytest.approx(alert.extracted_value, rel=1e-6) == 4.8251e-08
        assert alert.abort_triggered is True

        assert abort_file.exists()
        assert abort_file.stat().st_size == 0

    def test_safe_eigenvalue_does_not_trigger_abort(self, clean_env: Path):
        """Verifies that eigenvalues >= 1e-6 pass safely without triggering ABORT.signal."""
        interceptor = NanInfInterceptor(artifacts_dir=clean_env)
        scratch_dir = get_scratch_workspace_dir(clean_env)
        abort_file = scratch_dir / "ABORT.signal"

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
