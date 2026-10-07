"""Audit regressions use real files and measured process observations."""

import hashlib
import os
import time

import h5py
import psutil
import pytest

from cochem_base.cochem_core.ai.cochem_audit_runner import (
    PhysicalAuditUnavailableError,
    execute_audit,
    validate_physical_api_response,
    verify_immutable_pid_sampling,
    verify_physical_lttb_decimation,
)
from cochem_base.cochem_core.ai.inference_engine import DryRunEngine


def test_missing_archive_and_datasets_fail_without_substitution(tmp_path):
    with pytest.raises(PhysicalAuditUnavailableError, match="absent"):
        execute_audit(tmp_path)
    archive = tmp_path / "landscape.h5"
    with h5py.File(archive, "w") as handle:
        handle.attrs["purpose"] = "empty-input rejection"
    with pytest.raises(PhysicalAuditUnavailableError, match="Cannot load"):
        verify_physical_lttb_decimation(archive)


@pytest.mark.parametrize("threshold", [True, 2, 501, 500.0])
def test_audit_cannot_exceed_the_context_budget(tmp_path, threshold):
    with pytest.raises(ValueError, match="500-point"):
        verify_physical_lttb_decimation(tmp_path / "not-read.h5", threshold=threshold)


def test_lttb_audits_actual_process_observations(tmp_path):
    process = psutil.Process()
    observations = [(time.monotonic(), process.memory_info().rss) for _ in range(1200)]
    archive = tmp_path / "process-observations.h5"
    with h5py.File(archive, "w") as handle:
        handle.attrs["source_pid"] = process.pid
        handle.attrs["provenance"] = "psutil memory_info sampled on this machine"
        handle["process/time"] = [row[0] for row in observations]
        handle["process/rss"] = [row[1] for row in observations]
    report = verify_physical_lttb_decimation(
        archive, x_dataset="/process/time", y_dataset="/process/rss",
    )
    assert report["input_points"] == len(observations)
    assert report["output_points"] == 500
    assert report["source_sha256"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert report["elapsed_ms"] >= 0


def test_nonfinite_source_observations_fail(tmp_path):
    archive = tmp_path / "invalid-observations.h5"
    with h5py.File(archive, "w") as handle:
        handle["time"] = [time.monotonic() + i for i in range(3)]
        handle["rss"] = [psutil.Process().memory_info().rss, float("nan"), float("inf")]
    with pytest.raises(PhysicalAuditUnavailableError, match="finite"):
        verify_physical_lttb_decimation(archive, x_dataset="time", y_dataset="rss", threshold=3)


def test_actual_offline_engine_output_cannot_pass_a_network_audit():
    engine = DryRunEngine()
    try:
        response = engine.generate("Connectivity acknowledgement")
        with pytest.raises(PhysicalAuditUnavailableError, match="live API"):
            validate_physical_api_response(response)
    finally:
        engine.unload()


def test_pid_audit_reports_measured_status_and_memory():
    record = verify_immutable_pid_sampling()
    assert record["pid"] == os.getpid()
    assert record["rss_bytes"] > 0
