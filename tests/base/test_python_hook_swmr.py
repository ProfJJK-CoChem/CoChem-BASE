"""Physical CLI crash diagnostics and the exported HDF5 access boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import h5py
import numpy as np
import pytest

from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager
from cochem_base.core_engine.cochem_core_telemetry_logger import (
    safe_h5py_open,
    verify_provenance_signature,
)


def _child(source: str, *arguments: object, environment: dict[str, str] | None = None):
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source), *(str(value) for value in arguments)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )


def test_cli_import_does_not_arm_exception_hook() -> None:
    child = _child("""
        import sys
        original = sys.excepthook
        import cochem_base.cli
        assert sys.excepthook is original
        print("CLI import preserved the caller's exception hook")
    """)
    assert child.returncode == 0, child.stderr
    assert "preserved" in child.stdout


def test_cli_uncaught_error_records_signed_diagnostics_and_closes_hdf5(tmp_path: Path) -> None:
    """A malformed on-disk registry triggers a genuine CLI Python exception."""
    artifact_dir = tmp_path / "artifacts"
    registry_dir = artifact_dir / "Registry"
    registry_dir.mkdir(parents=True)
    # The CLI expects a mapping; this actual invalid JSON shape exercises its
    # uncaught-error boundary without replacing any CLI or telemetry function.
    (registry_dir / "cochem_system_config.json").write_text('["invalid registry shape"]')
    h5_path = tmp_path / "open-at-crash.h5"
    scratch = tmp_path / "scratch"
    secret = "physical-cli-crash-boundary-test"
    environment = dict(os.environ, COCHEM_SCRATCH_DIR=str(scratch),
                       COCHEM_TELEMETRY_SECRET_KEY=secret)
    child = _child("""
        import sys
        import h5py
        from cochem_base.cli import entrypoint
        opened = h5py.File(sys.argv[2], "w", libver="latest")
        opened.create_dataset("persisted", data=[1.25, 2.5, 5.0])
        sys.argv = ["cochem-cli", "status", "--artifact-dir", sys.argv[1], "--json"]
        raise SystemExit(entrypoint())
    """, artifact_dir, h5_path, environment=environment)

    assert child.returncode == 1
    assert "Global Telemetry crash excepthook armed" in child.stderr
    assert "Traceback (most recent call last)" in child.stderr
    assert "AttributeError" in child.stderr
    assert "Enforced emergency crash closure on open HDF5 file" in child.stderr
    stream = scratch / "CoChem_Artifacts" / "Logs" / "cochem_telemetry_stream.jsonl"
    entries = [json.loads(line) for line in stream.read_text().splitlines()]
    crashes = [entry for entry in entries if entry.get("event_type") == "UNHANDLED_PYTHON_CRASH"]
    assert len(crashes) == 1
    crash = crashes[0]
    assert crash["exception_type"] == "AttributeError"
    assert crash["status"] == "CRASHED"
    assert "action_status" in "".join(crash["traceback"])
    assert crash["pid"] > 0
    assert crash["hardware_metrics"]["timestamp_epoch_ms"] > 0
    assert verify_provenance_signature(crash, secret)
    with h5py.File(h5_path, "r") as recovered:
        assert list(recovered["persisted"][:]) == [1.25, 2.5, 5.0]


def test_safe_hdf5_swmr_reader_observes_live_canonical_writer(tmp_path: Path) -> None:
    path = tmp_path / "live.h5"
    manager = CoChemHDF5Manager(h5_path=path, ipc_db_path=tmp_path / "ipc.sqlite")
    manager.init_swmr_dataset("live_values", (0,), (None,), (4,))
    with manager.swmr_writer() as writer:
        for values in ([1.0, 2.0], [3.0]):
            manager.append_swmr_chunk("live_values", np.asarray(values), writer_file=writer)
            child = _child("""
                import json
                import sys
                from cochem_base.core_engine.cochem_core_telemetry_logger import safe_h5py_open
                with safe_h5py_open(sys.argv[1], "r", swmr=True) as reader:
                    assert reader.swmr_mode
                    reader["live_values"].refresh()
                    print(json.dumps(reader["live_values"][:].tolist()))
                assert not reader.id.valid
            """, path)
            assert child.returncode == 0, child.stderr
            expected = [1.0, 2.0] if len(values) == 2 else [1.0, 2.0, 3.0]
            assert json.loads(child.stdout) == expected


@pytest.mark.parametrize("mode", ["w", "a", "r+"])
def test_safe_hdf5_rejects_swmr_write_flag(tmp_path: Path, mode: str) -> None:
    with pytest.raises(ValueError, match="CoChemHDF5Manager.swmr_writer"):
        with safe_h5py_open(tmp_path / "guard.h5", mode, swmr=True):
            pytest.fail("SWMR writes must use the canonical manager")
    assert not (tmp_path / "guard.h5").exists()


def test_safe_hdf5_rejects_earliest_swmr_reader_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="libver='latest'"):
        with safe_h5py_open(tmp_path / "guard.h5", "r", swmr=True, libver="earliest"):
            pytest.fail("SWMR readers require the latest format")


def test_safe_hdf5_refuses_worker_write_without_creating_file(tmp_path: Path) -> None:
    path = tmp_path / "worker.h5"
    child = _child("""
        import sys
        from cochem_base.core.cochem_core_hdf5_manager import NonMasterWriteRejectionError
        from cochem_base.core_engine.cochem_core_telemetry_logger import safe_h5py_open
        try:
            with safe_h5py_open(sys.argv[1], "w"):
                raise AssertionError("worker gained a writer")
        except NonMasterWriteRejectionError:
            print("Worker write rejected")
        else:
            raise AssertionError("worker write was not rejected")
    """, path, environment=dict(os.environ, COCHEM_IS_MASTER="false"))
    assert child.returncode == 0, child.stderr
    assert "Worker write rejected" in child.stdout
    assert not path.exists()
    assert not Path(str(path) + ".lock").exists()


def test_safe_hdf5_owns_canonical_writer_lock_and_releases_on_error(tmp_path: Path) -> None:
    path = tmp_path / "locked.h5"
    probe = """
        import sys
        from filelock import FileLock, Timeout
        try:
            with FileLock(sys.argv[1], timeout=0):
                print("acquired")
        except Timeout:
            print("held")
    """
    with pytest.raises(RuntimeError, match="actual context failure"):
        with safe_h5py_open(path, "w", libver="latest") as writer:
            writer.create_dataset("values", data=[7, 8, 9])
            child = _child(probe, str(path.resolve()) + ".lock")
            assert child.returncode == 0, child.stderr
            assert child.stdout.strip() == "held"
            raise RuntimeError("actual context failure")
    assert not writer.id.valid
    child = _child(probe, str(path.resolve()) + ".lock")
    assert child.returncode == 0, child.stderr
    assert child.stdout.strip() == "acquired"
    with safe_h5py_open(path, "r") as reader:
        assert list(reader["values"][:]) == [7, 8, 9]
    assert not reader.id.valid
