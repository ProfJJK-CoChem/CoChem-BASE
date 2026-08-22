"""Comprehensive Zero-Mock test suite for cochem_base.interfaces.cochem_dock_main.

Validates FastAPI endpoints, Pydantic telemetry and job models, Dual-Mode Job Queue
(SQLite WAL vs. JSONL + FileLock), LTTB downsampling algorithm, WebSocket datagram
telemetry streaming, control frames, and path sanitization.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient

import interfaces.cochem_dock_main as legacy_dock_main
from cochem_base.interfaces.cochem_dock_main import (
    DualModeJobQueue,
    HealthResponse,
    JobCancelResponse,
    JobListResponse,
    JobStatusResponse,
    JobSubmitRequest,
    JobSubmitResponse,
    TelemetryBatchPayload,
    TelemetryEvent,
    TelemetryStatsResponse,
    app,
    create_app,
    default_job_queue,
    health_check,
    lifespan,
    logger,
    lttb_decimate,
    run_server,
    telemetry_stats,
    websocket_telemetry,
)
from cochem_base.path_sanitization import leak_patterns
from cochem_base.telemetry_transport import send_telemetry_payload


@pytest.fixture
def dock_main_path() -> Path:
    """Return the absolute path to cochem_base/interfaces/cochem_dock_main.py."""
    path = Path(__file__).resolve().parent.parent / "cochem_base" / "interfaces" / "cochem_dock_main.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def interfaces_dock_main_path() -> Path:
    """Return the absolute path to interfaces/cochem_dock_main.py."""
    path = Path(__file__).resolve().parent.parent / "interfaces" / "cochem_dock_main.py"
    assert path.is_file(), f"Target file does not exist: {path}"
    return path


@pytest.fixture
def client() -> TestClient:
    """Return a TestClient instance for the FastAPI application."""
    return TestClient(app)


def test_file_encoding_and_lf_line_endings(
    dock_main_path: Path, interfaces_dock_main_path: Path
) -> None:
    """Verify strictly Unix LF line endings (\\n), standard UTF-8 encoding, and no BOM."""
    for path in (dock_main_path, interfaces_dock_main_path):
        raw = path.read_bytes()
        assert b"\r\n" not in raw, f"Found Windows CRLF line endings in {path.name}"
        assert b"\n" in raw, f"Missing newline characters in {path.name}"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"Found UTF-8 BOM marker in {path.name}"

        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, f"File content in {path.name} is unexpectedly small."


def test_zero_personal_path_leaks(
    dock_main_path: Path, interfaces_dock_main_path: Path
) -> None:
    """Verify zero personal machine or local user path leakage in cochem_dock_main.py."""
    patterns = leak_patterns()
    for path in (dock_main_path, interfaces_dock_main_path):
        lines = path.read_text(encoding="utf-8").splitlines()
        leaks = []
        for lineno, line in enumerate(lines, 1):
            for pattern, placeholder in patterns:
                if pattern.search(line):
                    leaks.append((lineno, placeholder, line.strip()))

        assert len(leaks) == 0, f"Detected personal path leaks in {path.name}: {leaks}"


def test_interfaces_dock_main_reexports_and_aliases() -> None:
    """Verify interfaces.cochem_dock_main cleanly re-exports canonical symbols."""
    assert legacy_dock_main.app is app
    assert legacy_dock_main.create_app is create_app
    assert legacy_dock_main.health_check is health_check
    assert legacy_dock_main.telemetry_stats is telemetry_stats
    assert legacy_dock_main.websocket_telemetry is websocket_telemetry
    assert legacy_dock_main.lttb_decimate is lttb_decimate
    assert legacy_dock_main.run_server is run_server
    assert legacy_dock_main.lifespan is lifespan
    assert legacy_dock_main.logger is logger
    assert legacy_dock_main.default_job_queue is default_job_queue
    assert legacy_dock_main.DualModeJobQueue is DualModeJobQueue
    assert legacy_dock_main.TelemetryEvent is TelemetryEvent
    assert legacy_dock_main.TelemetryMessage is TelemetryEvent
    assert legacy_dock_main.HealthResponse is HealthResponse
    assert legacy_dock_main.TelemetryBatchPayload is TelemetryBatchPayload
    assert legacy_dock_main.TelemetryStatsResponse is TelemetryStatsResponse
    assert legacy_dock_main.JobSubmitRequest is JobSubmitRequest
    assert legacy_dock_main.JobSubmitResponse is JobSubmitResponse
    assert legacy_dock_main.JobStatusResponse is JobStatusResponse
    assert legacy_dock_main.JobCancelResponse is JobCancelResponse

    for sym in legacy_dock_main.__all__:
        assert hasattr(legacy_dock_main, sym), f"Missing symbol {sym} in legacy module"


def test_telemetry_event_model_fields_and_validation() -> None:
    """Verify TelemetryEvent field types, defaults, and extra attribute allowance."""
    event_data = {
        "type": "scf_step",
        "step": 4,
        "energy_hartree": -76.4321,
        "delta_energy": -0.00012,
        "max_gradient": 0.000045,
        "rms_gradient": 0.000012,
        "walltime_seconds": 1.24,
        "timestamp": 1700000000.0,
        "job_id": "test_job_123",
        "custom_metadata": "dft_pbe0",
    }
    event = TelemetryEvent.model_validate(event_data)
    assert event.type == "scf_step"
    assert event.step == 4
    assert event.energy_hartree == -76.4321
    assert event.delta_energy == -0.00012
    assert event.max_gradient == 0.000045
    assert event.rms_gradient == 0.000012
    assert event.walltime_seconds == 1.24
    assert event.timestamp == 1700000000.0
    assert event.job_id == "test_job_123"
    assert event.model_extra is not None
    assert event.model_extra.get("custom_metadata") == "dft_pbe0"

    # Verify JSON serialization
    serialized = event.model_dump_json()
    assert '"type":"scf_step"' in serialized
    assert '"energy_hartree":-76.4321' in serialized


def test_health_and_batch_payload_models() -> None:
    """Verify HealthResponse and TelemetryBatchPayload model contracts."""
    health = HealthResponse(
        status="online",
        service="CoChem-DOCK FastAPI",
        transport="udp",
        version="0.1.0",
        uptime_seconds=42.5,
        queue_mode="sqlite",
    )
    assert health.status == "online"
    assert health.transport == "udp"
    assert health.uptime_seconds == 42.5
    assert health.queue_mode == "sqlite"

    batch = TelemetryBatchPayload(
        type="lttb_batch",
        data=['{"type": "scf_step", "energy_hartree": -1.0}'],
        count=1,
    )
    assert batch.type == "lttb_batch"
    assert batch.count == 1
    assert len(batch.data) == 1


def test_job_models_contracts() -> None:
    """Verify Job schemas and validation contracts."""
    req = JobSubmitRequest(
        job_id="custom_01",
        engine="ORCA",
        input_file="input.xyz",
        calculation_type="optimization",
        parameters={"method": "PBE0", "basis": "def2-SVP"},
        priority=5,
    )
    assert req.job_id == "custom_01"
    assert req.engine == "ORCA"
    assert req.priority == 5

    res = JobSubmitResponse(
        job_id="custom_01",
        status="queued",
        message="Job queued successfully",
        queue_mode="sqlite",
        created_at=100.0,
    )
    assert res.status == "queued"

    status = JobStatusResponse(
        job_id="custom_01",
        status="running",
        progress=0.45,
        message="Iteration 4",
        engine="ORCA",
        calculation_type="optimization",
        created_at=100.0,
        updated_at=105.0,
        result={"energy": -76.4},
    )
    assert status.progress == 0.45
    assert status.result == {"energy": -76.4}

    cancel = JobCancelResponse(
        job_id="custom_01",
        status="cancelled",
        message="Job cancelled",
        cancelled=True,
    )
    assert cancel.cancelled is True


# --- LTTB Decimation Algorithm Unit Tests ---


def test_lttb_decimate_empty_or_zero_threshold() -> None:
    """Verify LTTB behavior on empty input or non-positive thresholds."""
    data = ['{"type": "scf_step", "energy_hartree": -76.0}']
    assert lttb_decimate([], 10) == []
    assert lttb_decimate(data, 0) == data
    assert lttb_decimate(data, -5) == data


def test_lttb_decimate_threshold_greater_than_data() -> None:
    """Verify LTTB returns all data when threshold >= number of items."""
    data = [
        json.dumps({"type": "scf_step", "energy_hartree": -76.0 - i * 0.1})
        for i in range(10)
    ]
    assert lttb_decimate(data, 10) == data
    assert lttb_decimate(data, 20) == data


def test_lttb_decimate_threshold_1_and_2() -> None:
    """Verify LTTB handles edge thresholds 1 and 2 safely."""
    data = [
        json.dumps({"type": "scf_step", "energy_hartree": -76.0 - i * 0.1})
        for i in range(10)
    ]
    res_1 = lttb_decimate(data, 1)
    assert len(res_1) == 1
    assert json.loads(res_1[0])["energy_hartree"] == -76.0

    res_2 = lttb_decimate(data, 2)
    assert len(res_2) == 2
    assert json.loads(res_2[0])["energy_hartree"] == -76.0
    assert json.loads(res_2[-1])["energy_hartree"] == -76.0 - 9 * 0.1


def test_lttb_decimate_preserves_first_last_and_peaks() -> None:
    """Verify LTTB downsampling retains first, last, and prominent peak extrema."""
    # Generate 50 points with a distinct peak at index 25
    points: List[str] = []
    for i in range(50):
        # Baseline curve with an abrupt sharp peak at i=25
        energy = -76.0 - (i * 0.01)
        if i == 25:
            energy = -74.0  # Sharp positive spike
        points.append(json.dumps({"type": "scf_step", "energy_hartree": energy}))

    threshold = 10
    decimated = lttb_decimate(points, threshold)
    assert len(decimated) == threshold

    # Verify first and last points are strictly preserved
    assert json.loads(decimated[0])["energy_hartree"] == -76.0
    assert json.loads(decimated[-1])["energy_hartree"] == -76.0 - (49 * 0.01)

    # Verify the sharp spike at index 25 is captured in the downsampled subset
    decimated_energies = [json.loads(p)["energy_hartree"] for p in decimated]
    assert -74.0 in decimated_energies, "LTTB failed to capture prominent peak"


def test_lttb_decimate_preserves_non_scf_messages() -> None:
    """Verify non-scf_step telemetry messages are preserved in the stream."""
    stream: List[str] = [
        '{"type": "init", "solver": "ORCA"}',
        '{"type": "scf_step", "energy_hartree": -10.0}',
        '{"type": "scf_step", "energy_hartree": -10.5}',
        '{"type": "scf_step", "energy_hartree": -10.8}',
        '{"type": "scf_step", "energy_hartree": -10.9}',
        '{"type": "status_update", "converged": true}',
        'malformed non-json log message',
    ]
    decimated = lttb_decimate(stream, threshold=2)
    # Threshold=2 on 4 scf points should keep 2 scf points + 3 non-scf items = 5 total
    assert len(decimated) == 5
    assert '{"type": "init", "solver": "ORCA"}' in decimated
    assert '{"type": "status_update", "converged": true}' in decimated
    assert "malformed non-json log message" in decimated


# --- Dual-Mode Job Queue Tests ---


def test_dual_mode_job_queue_sqlite(tmp_path: Path) -> None:
    """Verify SQLite WAL mode execution queue operations."""
    q = DualModeJobQueue(mode="sqlite", base_dir=tmp_path / "sqlite_test")
    assert q.mode == "sqlite"

    # Submit job
    req = JobSubmitRequest(
        job_id="job_sql_1",
        engine="ORCA",
        input_file="opt.xyz",
        calculation_type="opt",
        parameters={"functional": "B3LYP"},
        priority=10,
    )
    submit_res = q.submit_job(req)
    assert submit_res.job_id == "job_sql_1"
    assert submit_res.status == "queued"

    # Get status
    st = q.get_job_status("job_sql_1")
    assert st is not None
    assert st.status == "queued"
    assert st.engine == "ORCA"

    # Update status
    updated = q.update_job_status("job_sql_1", status="running", progress=0.5, message="SCF Cycle 10")
    assert updated is True
    st_updated = q.get_job_status("job_sql_1")
    assert st_updated is not None
    assert st_updated.status == "running"
    assert st_updated.progress == 0.5
    assert st_updated.message == "SCF Cycle 10"

    # List jobs
    all_jobs = q.list_jobs()
    assert len(all_jobs) >= 1
    assert any(j.job_id == "job_sql_1" for j in all_jobs)

    # Cancel job
    cancel_res = q.cancel_job("job_sql_1")
    assert cancel_res.status == "cancelled"
    st_cancelled = q.get_job_status("job_sql_1")
    assert st_cancelled is not None
    assert st_cancelled.status == "cancelled"


def test_dual_mode_job_queue_jsonl(tmp_path: Path) -> None:
    """Verify HPC JSONL + FileLock mode execution queue operations."""
    q = DualModeJobQueue(mode="jsonl", base_dir=tmp_path / "jsonl_test")
    assert q.mode == "jsonl"

    # Submit job
    req = JobSubmitRequest(
        job_id="job_hpc_1",
        engine="CFOUR",
        input_file="input.dat",
        calculation_type="vpt2",
        parameters={"basis": "cc-pVTZ"},
        priority=2,
    )
    submit_res = q.submit_job(req)
    assert submit_res.job_id == "job_hpc_1"
    assert submit_res.status == "queued"
    assert submit_res.queue_mode == "jsonl"

    # Get status
    st = q.get_job_status("job_hpc_1")
    assert st is not None
    assert st.status == "queued"
    assert st.engine == "CFOUR"

    # Update status
    updated = q.update_job_status(
        "job_hpc_1",
        status="completed",
        progress=1.0,
        result={"energy": -120.45},
        message="VPT2 Complete",
    )
    assert updated is True
    st_updated = q.get_job_status("job_hpc_1")
    assert st_updated is not None
    assert st_updated.status == "completed"
    assert st_updated.result == {"energy": -120.45}

    # List jobs
    all_jobs = q.list_jobs()
    assert len(all_jobs) >= 1
    assert any(j.job_id == "job_hpc_1" for j in all_jobs)

    # Cancel job
    cancel_res = q.cancel_job("job_hpc_1")
    assert cancel_res.status == "cancelled"


# --- REST API Endpoint Tests ---


def test_health_check_endpoint(client: TestClient) -> None:
    """Verify GET /api/health returns operational status and telemetry transport."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["service"] == "CoChem-DOCK FastAPI"
    assert data["transport"] in ("unix", "udp")
    assert "uptime_seconds" in data
    assert "queue_mode" in data


def test_health_check_function_direct_call() -> None:
    """Verify direct async call to health_check() function returns valid dictionary."""
    result = asyncio.run(health_check())
    assert isinstance(result, dict)
    assert result["status"] == "online"
    assert result["service"] == "CoChem-DOCK FastAPI"
    assert "transport" in result
    assert "queue_mode" in result


def test_telemetry_stats_endpoint(client: TestClient) -> None:
    """Verify GET /api/telemetry/stats returns transport details."""
    response = client.get("/api/telemetry/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["active"] is True
    assert data["transport"] in ("unix", "udp")
    assert "queue_mode" in data
    if data["transport"] == "unix":
        assert "socket_path" in data
    else:
        assert "udp_host" in data
        assert "udp_port" in data


def test_telemetry_stats_function_direct_call() -> None:
    """Verify direct async call to telemetry_stats() function."""
    stats = asyncio.run(telemetry_stats())
    assert isinstance(stats, dict)
    assert stats["active"] is True


def test_create_app_factory() -> None:
    """Verify create_app produces a valid configured FastAPI instance."""
    new_app = create_app()
    assert new_app.title == "CoChem-DOCK Telemetry API"


def test_rest_job_endpoints(client: TestClient) -> None:
    """Verify REST job submit, status, list, and cancel workflow."""
    # Submit job
    payload = {
        "job_id": "rest_test_01",
        "engine": "ORCA",
        "input_file": "mol.xyz",
        "calculation_type": "optimization",
        "parameters": {"functional": "r2scan-3c"},
        "priority": 1,
    }
    sub_res = client.post("/api/v1/jobs/submit", json=payload)
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["job_id"] == "rest_test_01"
    assert sub_data["status"] == "queued"

    # Status job
    stat_res = client.get("/api/v1/jobs/status/rest_test_01")
    assert stat_res.status_code == 200
    stat_data = stat_res.json()
    assert stat_data["job_id"] == "rest_test_01"
    assert stat_data["engine"] == "ORCA"

    # List jobs
    list_res = client.get("/api/v1/jobs?limit=50")
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["count"] >= 1

    # Cancel job
    cancel_res = client.post("/api/v1/jobs/cancel/rest_test_01")
    assert cancel_res.status_code == 200
    cancel_data = cancel_res.json()
    assert cancel_data["cancelled"] is True

    # 404 on missing job
    missing_res = client.get("/api/v1/jobs/status/non_existent_id")
    assert missing_res.status_code == 404


# --- WebSocket Telemetry Stream Tests ---


def test_websocket_ping_pong(client: TestClient) -> None:
    """Verify WebSocket client can send ping and receive pong."""
    with client.websocket_connect("/ws/telemetry") as ws:
        ws.send_text("ping")
        response = ws.receive_text()
        assert response == "pong"


def test_websocket_telemetry_datagram_transmission(client: TestClient) -> None:
    """Verify telemetry datagram sent via transport is received by connected WebSocket."""
    with client.websocket_connect("/ws/telemetry?buffer_threshold=100&decimate_target=20") as ws:
        # Send a real physical telemetry datagram payload
        payload = {"type": "scf_step", "energy_hartree": -76.42119, "step": 1}
        send_telemetry_payload(payload)

        # Receive the telemetry message over WebSocket
        received_raw = ws.receive_text()
        received_obj = json.loads(received_raw)
        assert received_obj["type"] == "scf_step"
        assert received_obj["energy_hartree"] == -76.42119
        assert received_obj["step"] == 1


def test_websocket_buffer_batching_and_flush(client: TestClient) -> None:
    """Verify WebSocket buffer batching and manual flush control frame."""
    with client.websocket_connect("/ws/telemetry?buffer_threshold=50&decimate_target=5") as ws:
        # Send a few telemetry events (below threshold)
        for i in range(3):
            send_telemetry_payload({"type": "scf_step", "energy_hartree": -76.0 - i, "step": i})
            # Read direct raw frame
            msg = ws.receive_text()
            assert json.loads(msg)["step"] == i

        # Test flush frame
        ws.send_text("flush")
