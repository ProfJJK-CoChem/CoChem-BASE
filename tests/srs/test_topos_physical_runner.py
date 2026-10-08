"""Physical runner boundaries; local contracts do not substitute for engine acceptance."""
from __future__ import annotations

import json
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest
from pydantic import ValidationError

from cochem_base.topos_runner import (
    TOPOSExecutionBroker,
    TOPOSSearchConfig,
    _parse_xyz,
    _run_worker,
    _terminate_tree,
    _write_json,
)

WATER = "3\nwater input\nO 0 0 0\nH 0.9572 0 0\nH -0.2399872 0.927297 0\n"


def test_search_requires_explicit_physical_input(tmp_path: Path) -> None:
    broker = TOPOSExecutionBroker(tmp_path / "scratch", tmp_path / "store")
    with pytest.raises(ValueError, match="physical input XYZ"):
        broker.launch_search(TOPOSSearchConfig())
    assert list(broker.scratch_root.iterdir()) == []


def test_search_missing_engine_fails_before_launch(tmp_path: Path) -> None:
    source = tmp_path / "water.xyz"
    source.write_text(WATER, encoding="utf-8")
    broker = TOPOSExecutionBroker(tmp_path / "scratch", tmp_path / "store")
    config = TOPOSSearchConfig(input_xyz_path=str(source), atom_count=3, protocol="GOAT", orca_binary=str(tmp_path / "absent-orca"))
    with pytest.raises(FileNotFoundError, match="physical ORCA"):
        broker.launch_search(config)
    assert not broker.active_processes
    assert list(broker.scratch_root.iterdir()) == []


def test_default_union_and_strict_parameters() -> None:
    assert TOPOSSearchConfig().protocol == "CREST_GOAT"
    with pytest.raises(ValidationError):
        TOPOSSearchConfig(protocol="EMT")
    with pytest.raises(ValidationError):
        TOPOSSearchConfig(max_hours=float("nan"))
    with pytest.raises(ValidationError):
        TOPOSSearchConfig(unknown_engine_option=True)


def test_input_atom_count_is_checked(tmp_path: Path) -> None:
    source = tmp_path / "water.xyz"
    source.write_text(WATER, encoding="utf-8")
    broker = TOPOSExecutionBroker(tmp_path / "scratch", tmp_path / "store")
    with pytest.raises(ValueError, match="atom_count"):
        broker.launch_search(TOPOSSearchConfig(input_xyz_path=str(source), atom_count=4))


@pytest.mark.parametrize("comment", ["water input", "energy=nan", "energy=-76.0 kcal/mol"])
def test_engine_ensemble_requires_explicit_finite_hartree_energy(tmp_path: Path, comment: str) -> None:
    path = tmp_path / "ensemble.xyz"
    path.write_text(WATER.replace("water input", comment), encoding="utf-8")
    with pytest.raises(ValueError):
        _parse_xyz(path, require_energy=True)


def test_native_ensemble_parser_preserves_energy_coordinates(tmp_path: Path) -> None:
    path = tmp_path / "ensemble.xyz"
    path.write_text(WATER.replace("water input", "-76.0123") + WATER.replace("water input", "energy=-76.0010 Hartree"), encoding="utf-8")
    frames = _parse_xyz(path, require_energy=True)
    assert [frame.energy for frame in frames] == [-76.0123, -76.001]
    assert frames[0].symbols == ("O", "H", "H")
    assert frames[0].coordinates[1, 0] == 0.9572


def test_incomplete_and_nonfinite_xyz_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "bad.xyz"
    path.write_text("3\n-76.0\nO 0 0 0\nH 1 0 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="incomplete"):
        _parse_xyz(path, require_energy=True)
    path.write_text(WATER.replace("0.9572", "nan"), encoding="utf-8")
    with pytest.raises(ValueError, match="Nonfinite"):
        _parse_xyz(path, require_energy=False)


def test_worker_failed_launch_records_failure_without_ensemble(tmp_path: Path) -> None:
    source = tmp_path / "input.xyz"
    source.write_text(WATER, encoding="utf-8")
    config = TOPOSSearchConfig(input_xyz_path=str(source), atom_count=3, protocol="GOAT", orca_binary=str(tmp_path / "missing-binary"))
    config_path = tmp_path / "config.json"
    _write_json(config_path, config.model_dump())
    _write_json(tmp_path / "telemetry.json", {"job_id": "topos_job_" + "a" * 32, "status": "RUNNING"})
    old_term = signal.getsignal(signal.SIGTERM)
    old_int = signal.getsignal(signal.SIGINT)
    try:
        assert _run_worker(config_path) == 1
    finally:
        signal.signal(signal.SIGTERM, old_term)
        signal.signal(signal.SIGINT, old_int)
    telemetry = json.loads((tmp_path / "telemetry.json").read_text())
    assert telemetry["status"] == "FAILED"
    assert "FileNotFoundError" in telemetry["error"]
    assert not (tmp_path / "conformer_ensemble.xyz").exists()


def test_promotion_rejects_running_jobs_and_traversal(tmp_path: Path) -> None:
    broker = TOPOSExecutionBroker(tmp_path / "scratch", tmp_path / "store")
    job_id = "topos_job_" + "b" * 32
    folder = broker.scratch_root / job_id
    folder.mkdir()
    _write_json(folder / "telemetry.json", {"status": "RUNNING"})
    with pytest.raises(RuntimeError, match="successfully completed"):
        broker.promote_artifacts(job_id)
    with pytest.raises(ValueError, match="identifier"):
        broker.poll_telemetry("../../other-job")


def test_process_cancellation_reaps_real_descendant(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "child.pid"
    script = "import subprocess,sys,time,pathlib; child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)"
    proc = subprocess.Popen([sys.executable, "-c", script, str(child_pid_path)])
    try:
        deadline = time.monotonic() + 5
        while not child_pid_path.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert child_pid_path.exists()
        child_pid = int(child_pid_path.read_text())
        _terminate_tree(proc)
        assert proc.poll() is not None
        assert not psutil.pid_exists(child_pid) or psutil.Process(child_pid).status() == psutil.STATUS_ZOMBIE
    finally:
        if proc.poll() is None:
            _terminate_tree(proc)


@pytest.mark.skipif(not (shutil.which("orca") and shutil.which("crest")), reason="Real licensed ORCA and CREST engines are required for union acceptance")
def test_physical_crest_goat_union(tmp_path: Path) -> None:
    source = tmp_path / "water.xyz"
    source.write_text(WATER, encoding="utf-8")
    broker = TOPOSExecutionBroker(tmp_path / "scratch", tmp_path / "store")
    job = broker.launch_search(TOPOSSearchConfig(input_xyz_path=str(source), atom_count=3, max_hours=0.05))
    deadline = time.monotonic() + 200
    try:
        while time.monotonic() < deadline:
            telemetry = broker.poll_telemetry(job)
            if telemetry["status"] == "FAILED":
                pytest.fail(telemetry["error"])
            process = broker.active_processes[job]
            if telemetry["status"] == "COMPLETED" and process.poll() == 0:
                break
            time.sleep(0.1)
        else:
            pytest.fail("Physical engines exceeded test deadline")
        assert set(telemetry["engines"]) == {"CREST", "GOAT"}
        assert telemetry["candidates_found"] >= telemetry["deduplicated_count"] >= 1
        assert broker.promote_artifacts(job)["ensemble_xyz"].is_file()
    finally:
        process = broker.active_processes[job]
        if process.poll() is None:
            broker.cancel_search(job)


def test_source_checkout_scratch_and_symlink_are_rejected(tmp_path: Path) -> None:
    import cochem_base.topos_runner as runner
    source_root = Path(runner.__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="outside the source checkout"):
        TOPOSExecutionBroker(source_root / "unexpected-scratch", tmp_path / "store")
    link = tmp_path / "source-link"
    try:
        link.symlink_to(source_root, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit directory symlinks")
    with pytest.raises(ValueError, match="outside the source checkout"):
        TOPOSExecutionBroker(tmp_path / "scratch", link / "unexpected-store")


def test_job_runtime_directory_override_cannot_be_ignored(tmp_path: Path) -> None:
    broker = TOPOSExecutionBroker(tmp_path / "scratch", tmp_path / "store")
    with pytest.raises(ValueError, match="broker constructor paths"):
        broker.launch_search(TOPOSSearchConfig(scratch_dir=str(tmp_path / "elsewhere")))
    with pytest.raises(ValueError, match="broker constructor paths"):
        broker.launch_search(TOPOSSearchConfig(store_dir=str(tmp_path / "elsewhere")))


def test_engine_unknown_energy_unit_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "ensemble.xyz"
    path.write_text(WATER.replace("water input", "E=-76.0 cm-1"), encoding="utf-8")
    with pytest.raises(ValueError, match="energy unit"):
        _parse_xyz(path, require_energy=True)
