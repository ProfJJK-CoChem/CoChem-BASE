"""Canonical broker admission and owned-process lifecycle regressions.

Lifecycle checks use real Python child processes and make no quantum-chemistry
result claim. Actual parallel CREST/GOAT acceptance is retained separately.
"""
from pathlib import Path
import subprocess
import sys

import pytest

from cochem_base.topos_runner import TOPOSExecutionBroker, TOPOSSearchConfig, _write_json


def test_missing_geometry_cannot_launch_a_search(tmp_path: Path):
    broker = TOPOSExecutionBroker(tmp_path / "scratch", tmp_path / "store")
    with pytest.raises(ValueError, match="physical input XYZ"):
        broker.launch_search(TOPOSSearchConfig(protocol="GOAT"))
    assert not broker.active_processes
    assert not list(broker.scratch_root.iterdir())


def _owned_process(broker):
    job_id = "topos_job_" + "a" * 32
    directory = broker.scratch_root / job_id
    directory.mkdir()
    _write_json(directory / "telemetry.json", {"job_id": job_id, "status": "RUNNING", "error": None})
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    broker.active_processes[job_id] = process
    return job_id, process


def test_live_process_cannot_promote_unmeasured_artifacts(tmp_path: Path):
    broker = TOPOSExecutionBroker(tmp_path / "scratch", tmp_path / "store")
    job_id, process = _owned_process(broker)
    try:
        assert broker.poll_telemetry(job_id)["status"] == "RUNNING"
        with pytest.raises(RuntimeError, match="Only successfully completed physical searches"):
            broker.promote_artifacts(job_id)
        assert not list(broker.store_root.iterdir())
    finally:
        if process.poll() is None:
            broker.cancel_search(job_id)


def test_cancellation_terminates_only_registered_owned_process(tmp_path: Path):
    broker = TOPOSExecutionBroker(tmp_path / "scratch", tmp_path / "store")
    job_id, process = _owned_process(broker)
    unrelated = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert broker.cancel_search(job_id)
        assert process.poll() is not None
        assert unrelated.poll() is None
        assert broker.poll_telemetry(job_id)["status"] == "CANCELLED"
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        unrelated.terminate()
        unrelated.wait(timeout=10)
