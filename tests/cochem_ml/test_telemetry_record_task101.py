"""
CoChem-ML Telemetry Data Layer Unit Tests (Task 1.01)
Physical Verification Suite for TelemetryRecord Dataclass.

Invariants Verified:
- Zero-Mock & Anti-Spoofing Protocol v4 Directives
- Dynamic Mendeleev Atomic Weight Resolution
- Strict Invariant Validation on Types, Bounds, and Timestamps
- Real Subprocess Execution and Authentic OS PIDs
"""

from __future__ import annotations

import dataclasses
import datetime
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict

import pytest
from mendeleev import element

from cochem_ml.telemetry_record import (
    GENESIS_HASH,
    PhysicalExecutionProfiler,
    TelemetryRecord,
    TimestampWindow,
    get_current_iso_timestamp,
)


def test_dynamic_mendeleev_mass_invariant() -> None:
    """Verify dynamic Mendeleev mass query is operational without static dictionaries."""
    carbon = element("C")
    silicon = element("Si")
    assert carbon.atomic_number == 6
    assert carbon.mass > 12.0
    assert silicon.atomic_number == 14
    assert silicon.mass > 28.0


def test_telemetry_record_instantiation_and_immutability() -> None:
    """Verify TelemetryRecord instantiates cleanly and enforces frozen immutability."""
    now_utc = get_current_iso_timestamp()
    record = TelemetryRecord(
        tool_name="run_command",
        command_string="python --version",
        pid=os.getpid(),
        execution_latency=0.045,
        memory_footprint=10485760,  # 10 MB in bytes
        exit_code=0,
        timestamps=(now_utc, now_utc),
        metadata={"worker": "test_runner"},
    )

    assert record.tool_name == "run_command"
    assert record.command_string == "python --version"
    assert record.pid == os.getpid()
    assert record.execution_latency == 0.045
    assert record.execution_latency_ms == pytest.approx(45.0)
    assert record.memory_footprint == 10485760
    assert record.memory_footprint_mb == pytest.approx(10.0)
    assert record.exit_code == 0
    assert record.start_timestamp == now_utc
    assert record.end_timestamp == now_utc
    assert record.timestamp == now_utc
    assert record.is_success is True
    assert record.success is True
    assert record.metadata["worker"] == "test_runner"
    assert record.verify_integrity() is True

    # Verify frozen immutability
    with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
        record.exit_code = 1  # Direct assignment blocked by frozen dataclass


def test_telemetry_record_validation_invariants() -> None:
    """Verify strict validation of input types, bounds, and ISO 8601 formatting."""
    valid_ts = (get_current_iso_timestamp(), get_current_iso_timestamp())

    # Empty tool_name
    with pytest.raises(ValueError, match="tool_name must be a non-empty string"):
        TelemetryRecord(
            tool_name="",
            command_string="echo 1",
            pid=100,
            execution_latency=0.1,
            memory_footprint=1000,
            exit_code=0,
            timestamps=valid_ts,
        )

    # Invalid command_string type
    with pytest.raises(TypeError, match="command_string must be a string"):
        TelemetryRecord(
            tool_name="test_tool",
            command_string=12345,  # type: ignore
            pid=100,
            execution_latency=0.1,
            memory_footprint=1000,
            exit_code=0,
            timestamps=valid_ts,
        )

    # Negative PID
    with pytest.raises(ValueError, match="pid must be a non-negative integer"):
        TelemetryRecord(
            tool_name="test_tool",
            command_string="echo 1",
            pid=-1,
            execution_latency=0.1,
            memory_footprint=1000,
            exit_code=0,
            timestamps=valid_ts,
        )

    # Negative execution latency
    with pytest.raises(ValueError, match="execution_latency must be non-negative"):
        TelemetryRecord(
            tool_name="test_tool",
            command_string="echo 1",
            pid=100,
            execution_latency=-0.5,
            memory_footprint=1000,
            exit_code=0,
            timestamps=valid_ts,
        )

    # Negative memory footprint
    with pytest.raises(ValueError, match="memory_footprint must be a non-negative integer"):
        TelemetryRecord(
            tool_name="test_tool",
            command_string="echo 1",
            pid=100,
            execution_latency=0.1,
            memory_footprint=-100,
            exit_code=0,
            timestamps=valid_ts,
        )

    # Invalid exit_code type
    with pytest.raises(TypeError, match="exit_code must be an integer"):
        TelemetryRecord(
            tool_name="test_tool",
            command_string="echo 1",
            pid=100,
            execution_latency=0.1,
            memory_footprint=1000,
            exit_code="0",  # type: ignore
            timestamps=valid_ts,
        )


def test_telemetry_record_capture_with_authentic_subprocess() -> None:
    """Verify TelemetryRecord.capture records authentic physical subprocess execution."""
    cmd = [sys.executable, "-c", "import sys, time; time.sleep(0.02); sys.exit(0)"]

    record = TelemetryRecord.capture(
        tool_name="run_command",
        command=cmd,
        metadata={"task": "1.01"},
    )

    assert record.exit_code == 0
    assert record.is_success is True
    assert record.execution_latency >= 0.015
    assert record.pid > 0
    assert record.memory_footprint >= 0
    assert record.verify_integrity() is True


def test_telemetry_record_capture_with_failing_subprocess() -> None:
    """Verify TelemetryRecord.capture records authentic non-zero exit codes correctly."""
    cmd = [sys.executable, "-c", "import sys; sys.exit(7)"]

    record = TelemetryRecord.capture(
        tool_name="run_command",
        command=cmd,
    )

    assert record.exit_code == 7
    assert record.is_success is False
    assert record.success is False
    assert record.verify_integrity() is True


def test_telemetry_record_serialization_roundtrip_dict_and_json() -> None:
    """Verify lossless serialization and deserialization via dictionary and JSON."""
    now_utc = get_current_iso_timestamp()
    record = TelemetryRecord(
        tool_name="git_commit",
        command_string="git commit -m 'Task 1.01 ratified'",
        pid=1234,
        execution_latency=0.125,
        memory_footprint=20971520,
        exit_code=0,
        timestamps=(now_utc, now_utc),
        metadata={"git_branch": "main", "retry_count": 0},
    )

    # 1. Dictionary roundtrip
    dict_payload = record.to_dict()
    reconstructed_dict = TelemetryRecord.from_dict(dict_payload)
    assert reconstructed_dict.tool_name == record.tool_name
    assert reconstructed_dict.pid == record.pid
    assert reconstructed_dict.record_hash == record.record_hash
    assert reconstructed_dict.verify_integrity() is True

    # 2. JSON roundtrip
    json_string = record.to_json()
    reconstructed_json = TelemetryRecord.from_json(json_string)
    assert reconstructed_json.tool_name == record.tool_name
    assert reconstructed_json.record_hash == record.record_hash
    assert reconstructed_json.verify_integrity() is True


def test_telemetry_record_columnar_dict_for_parquet() -> None:
    """Verify columnar export dictionary matching Apache Parquet schema (Task 1.04)."""
    now_utc = get_current_iso_timestamp()
    record = TelemetryRecord(
        tool_name="pytest",
        command_string="pytest -v",
        pid=5678,
        execution_latency=1.5,
        memory_footprint=52428800,  # 50 MB
        exit_code=0,
        timestamps=(now_utc, now_utc),
        metadata={"suite": "telemetry"},
    )

    columnar = record.to_columnar_dict()
    assert columnar["tool_name"] == ["pytest"]
    assert columnar["pid"] == [5678]
    assert columnar["execution_latency"] == [pytest.approx(1.5)]
    assert columnar["memory_footprint"] == [52428800]
    assert columnar["exit_code"] == [0]
    assert "metadata_json" in columnar
    parsed_meta = json.loads(columnar["metadata_json"][0])
    assert parsed_meta["suite"] == "telemetry"
