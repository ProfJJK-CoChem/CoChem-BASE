"""Chunk 17 REQ-BASE-003 / VR-07: real file locks and live HDF5 processes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import filelock
import h5py
import numpy as np
import pytest

from cochem_base.core.cochem_core_hdf5_manager import (
    CoChemHDF5Manager,
    FileLockTimeoutError,
    HDF5ManagerError,
    NonMasterWriteRejectionError,
    resolve_landscape_h5_path,
)
from cochem_base.core.cochem_core_registry_manager import AtomicFileLock


def _manager(tmp_path: Path, **kwargs) -> CoChemHDF5Manager:
    return CoChemHDF5Manager(
        h5_path=tmp_path / "complexes.h5", ipc_db_path=tmp_path / "ipc.db", **kwargs
    )


def _child(code: str, *args: object, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-c", code, *map(str, args)],
        check=True, capture_output=True, text=True, timeout=25, env=env,
    )


def test_live_writer_cannot_be_reaped_by_lock_age(tmp_path):
    """An aged lock remains exclusive until its actual owner releases it."""
    lock_path = tmp_path / "shared.lock"
    with AtomicFileLock(lock_path):
        old = time.time() - 3600
        os.utime(lock_path, (old, old))
        result = _child(
            """
import sys
from cochem_base.core.cochem_core_registry_manager import AtomicFileLock, CoChemLockTimeoutError
try:
    with AtomicFileLock(sys.argv[1], timeout=0.15, stale_timeout=0.01):
        raise AssertionError('Acquired a live writer lock')
except CoChemLockTimeoutError:
    print('blocked')
""", lock_path,
        )
        assert result.stdout.strip() == "blocked"
    # Releasing must preserve the inode used by waiting processes.
    inode = lock_path.stat().st_ino
    with filelock.FileLock(str(lock_path), timeout=0.2):
        assert lock_path.stat().st_ino == inode


def test_lock_ownership_released_after_process_crash(tmp_path):
    lock_path = tmp_path / "crashed.lock"
    _child(
        """
import os, sys
from cochem_base.core.cochem_core_registry_manager import AtomicFileLock
lock = AtomicFileLock(sys.argv[1])
lock.acquire()
os._exit(0)
""", lock_path,
    )
    with AtomicFileLock(lock_path, timeout=0.2):
        assert lock_path.exists()


def test_context_lock_does_not_steal_an_aged_live_lock(tmp_path):
    from cochem.core.context import FileLock

    lock_path = tmp_path / "context.lock"
    with FileLock(lock_path):
        old = time.time() - 3600
        os.utime(lock_path, (old, old))
        result = _child(
            """
import sys
from cochem.core.context import FileLock
try:
    FileLock(sys.argv[1], timeout_sec=0.15).acquire()
    raise AssertionError('Acquired an aged but live writer lock')
except TimeoutError:
    print('blocked')
""", lock_path,
        )
        assert result.stdout.strip() == "blocked"


def test_default_writer_timeout_is_ten_seconds(tmp_path):
    manager = _manager(tmp_path)
    assert manager.lock_timeout == 10.0
    assert manager.gatekeeper.lock_path == manager.lock_path
    assert manager.gatekeeper.lock_timeout == 10.0
    with AtomicFileLock(manager.lock_path):
        result = _child(
            """
import sys, time
from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager, FileLockTimeoutError
manager = CoChemHDF5Manager(h5_path=sys.argv[1], ipc_db_path=sys.argv[2])
start = time.monotonic()
try:
    with manager.swmr_writer():
        raise AssertionError('Acquired a competing writer lock')
except FileLockTimeoutError:
    print(time.monotonic() - start)
""", manager.h5_path, manager.ipc_queue.db_path,
        )
    assert 9.5 <= float(result.stdout.strip()) < 15


def test_multiple_processes_observe_each_flushed_chunk(tmp_path):
    """Three persistent reader processes see complete trajectory/energy/gradient rows."""
    manager = _manager(tmp_path)
    for name in ("trajectory", "energy", "gradient"):
        manager.init_swmr_dataset(name, (0, 3), (None, 3), (8, 3))
    readers = []
    pool = ThreadPoolExecutor(max_workers=3)
    with manager.swmr_writer() as writer:
        try:
            for _ in range(3):
                readers.append(subprocess.Popen(
                    [sys.executable, "-u", "-c", """
import json, sys
from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager
manager = CoChemHDF5Manager(h5_path=sys.argv[1], ipc_db_path=sys.argv[2])
with manager.swmr_reader() as reader:
    print('ready', flush=True)
    for command in sys.stdin:
        if command.strip() == 'stop':
            break
        print(json.dumps({name: manager.read_swmr_dataset(name, reader_file=reader).tolist()
                          for name in ('trajectory', 'energy', 'gradient')}), flush=True)
""", str(manager.h5_path), str(manager.ipc_queue.db_path)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                ))
            # Bound reads so a protocol or locking failure cannot hang the suite.
            for future in [pool.submit(reader.stdout.readline) for reader in readers]:
                assert future.result(timeout=20).strip() == "ready"
            for step in range(10):
                block = np.full((1, 3), float(step))
                for name in ("trajectory", "energy", "gradient"):
                    manager.append_swmr_chunk(name, block, writer_file=writer)
                for reader in readers:
                    reader.stdin.write("read\n")
                    reader.stdin.flush()
                for future in [pool.submit(reader.stdout.readline) for reader in readers]:
                    snapshot = json.loads(future.result(timeout=5))
                    for rows in snapshot.values():
                        np.testing.assert_array_equal(rows, np.repeat(np.arange(step + 1)[:, None], 3, axis=1))
            for reader in readers:
                reader.stdin.write("stop\n")
                reader.stdin.flush()
                assert reader.wait(timeout=10) == 0, reader.stderr.read()
        finally:
            for reader in readers:
                if reader.poll() is None:
                    reader.kill()
                reader.communicate(timeout=5)
            pool.shutdown(wait=True)
    report = manager.verify_file_integrity()
    assert report["valid_datasets"] == 3
    assert not report["corrupted_datasets"]
    assert not report["filter_violations"]


def test_rejected_append_and_reinitialization_preserve_existing_data(tmp_path):
    manager = _manager(tmp_path)
    manager.init_swmr_dataset("energy", (1, 3), (None, 3), (8, 3), initial_data=np.ones((1, 3)))
    for invalid in (np.ones((1, 2)), np.array([["not-a-number"] * 3])):
        with pytest.raises((ValueError, TypeError)):
            manager.append_swmr_chunk("energy", invalid)
        np.testing.assert_array_equal(manager.read_swmr_dataset("energy"), np.ones((1, 3)))
    with pytest.raises(HDF5ManagerError, match="already exists"):
        manager.init_swmr_dataset("energy", (0, 3), (None, 3), (8, 3))
    np.testing.assert_array_equal(manager.read_swmr_dataset("energy"), np.ones((1, 3)))
    with h5py.File(manager.h5_path, "r+", libver="latest") as foreign_writer:
        with pytest.raises(HDF5ManagerError, match="active swmr_writer"):
            manager.append_swmr_chunk("energy", np.ones((1, 3)), writer_file=foreign_writer)


def test_workers_cannot_bypass_master_gate_using_swmr(tmp_path):
    manager = _manager(tmp_path)
    manager.init_swmr_dataset("energy", (0,), (None,), (8,))
    code = """
import sys
from pathlib import Path
import numpy as np
import pytest
from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager, NonMasterWriteRejectionError
root = Path(sys.argv[1])
manager = CoChemHDF5Manager(h5_path=root / 'complexes.h5', ipc_db_path=root / 'ipc.db')
with pytest.raises(NonMasterWriteRejectionError):
    manager.init_swmr_dataset('other', (0,), (None,), (8,))
with pytest.raises(NonMasterWriteRejectionError):
    manager.append_swmr_chunk('energy', np.array([1.0]))
with pytest.raises(NonMasterWriteRejectionError):
    with manager.swmr_writer():
        pass
with pytest.raises(NonMasterWriteRejectionError):
    with manager.transaction('w-'):
        pass
"""
    _child(code, tmp_path, env={**os.environ, "COCHEM_IS_MASTER": "0"})
    assert manager.read_swmr_dataset("energy").shape == (0,)
    with h5py.File(manager.h5_path, "r") as handle:
        assert "other" not in handle


def test_failed_dataset_replacement_preserves_previous_values(tmp_path):
    manager = _manager(tmp_path)
    manager.write_dataset_filtered("results", "energies", [-75.0, -76.0])
    with pytest.raises(TypeError):
        manager.write_dataset_filtered("results", "energies", np.array([object()], dtype=object))
    with pytest.raises(TypeError):
        manager.write_dataset_filtered("results", "energies", [-90.0], attrs={"invalid": object()})
    with manager.transaction("r") as handle:
        np.testing.assert_array_equal(handle["results/energies"][:], [-75.0, -76.0])
        assert list(handle["results"]) == ["energies"]


def test_telemetry_path_prefers_chunk17_and_preserves_legacy_store(tmp_path):
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"COCHEM_COMPLEXES_H5", "COCHEM_LANDSCAPE_H5"}}
    environment.update(COCHEM_ARTIFACTS=str(tmp_path), COCHEM_ARTIFACT_DIR=str(tmp_path))
    code = """
import sys
from pathlib import Path
import h5py
from cochem_base.core.cochem_core_hdf5_manager import resolve_landscape_h5_path
primary = Path(sys.argv[1]) / 'Databases' / 'complexes.h5'
legacy = primary.with_name('landscape.h5')
assert resolve_landscape_h5_path() == primary
with h5py.File(legacy, 'w'):
    pass
assert resolve_landscape_h5_path() == legacy
with h5py.File(primary, 'w'):
    pass
assert resolve_landscape_h5_path() == primary
"""
    _child(code, tmp_path, env=environment)
    primary = tmp_path / "Databases" / "complexes.h5"
    legacy = primary.with_name("landscape.h5")
    assert primary.is_file() and legacy.is_file()
    _child("from cochem_base.core.cochem_core_hdf5_manager import resolve_landscape_h5_path; from pathlib import Path; import sys; assert resolve_landscape_h5_path() == Path(sys.argv[1])",
           legacy, env={**environment, "COCHEM_LANDSCAPE_H5": str(legacy)})


def test_pes_reader_cannot_enter_while_another_process_writes(tmp_path):
    from cochem_base.core_engine.cochem_core_pes_store import ReadWriteFileLock

    path = tmp_path / "pes.h5.lock"
    with ReadWriteFileLock(path).write_lock():
        child = _child(
            """
import sys
from cochem_base.core_engine.cochem_core_pes_store import ReadWriteFileLock
from cochem_base.exceptions import HDF5LockTimeoutError
try:
    with ReadWriteFileLock(sys.argv[1], timeout=0.15).read_lock():
        raise AssertionError('Reader entered while a foreign writer owns the file')
except HDF5LockTimeoutError:
    print('blocked')
""", path,
        )
        assert child.stdout.strip() == "blocked"


def test_pes_writer_waits_for_foreign_reader_and_then_recovers(tmp_path):
    from cochem_base.core_engine.cochem_core_pes_store import ReadWriteFileLock

    path = tmp_path / "pes.h5.lock"
    with ReadWriteFileLock(path).read_lock():
        child = _child(
            """
import sys
from cochem_base.core_engine.cochem_core_pes_store import ReadWriteFileLock
from cochem_base.exceptions import HDF5LockTimeoutError
try:
    with ReadWriteFileLock(sys.argv[1], timeout=0.15).write_lock():
        raise AssertionError('Writer entered while a foreign reader owns the file')
except HDF5LockTimeoutError:
    print('blocked')
""", path,
        )
        assert child.stdout.strip() == "blocked"
    with ReadWriteFileLock(path, timeout=0.15).write_lock():
        assert not list(path.with_name(path.name + ".readers").glob("*.token"))


def test_healer_preserves_live_owner_even_when_database_is_unhealthy(tmp_path):
    from cochem_base.cochem_h5_healer import create_swmr_lock, force_release_swmr, get_lease_metadata_path

    database = tmp_path / "unhealthy.h5"
    database.touch()
    lock_path = create_swmr_lock(database)
    before = lock_path.read_bytes()
    result = force_release_swmr(database)
    assert result["status"] == "LOCK_ACTIVE"
    assert result["lock_released"] is False
    assert result["file_healthy"] is False
    assert lock_path.read_bytes() == before
    assert get_lease_metadata_path(database).exists()


def test_healer_reaps_only_after_actual_owner_process_exits(tmp_path):
    from cochem_base.cochem_h5_healer import force_release_swmr, get_lease_metadata_path, get_lock_file_path

    database = tmp_path / "crashed_owner.h5"
    with h5py.File(database, "w"):
        pass
    owner = subprocess.Popen(
        [sys.executable, "-u", "-c", """
import sys
from cochem_base.cochem_h5_healer import create_swmr_lock
create_swmr_lock(sys.argv[1])
print('ready', flush=True)
sys.stdin.readline()
""", str(database)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(owner.stdout.readline).result(timeout=20).strip() == "ready"
        assert force_release_swmr(database)["lock_released"] is False
        owner.communicate("exit\n", timeout=10)
        assert owner.returncode == 0
        released = force_release_swmr(database)
        assert released["lock_released"] is True
        assert released["reaped_pids"] == [owner.pid]
        assert not get_lock_file_path(database).exists()
        assert not get_lease_metadata_path(database).exists()
    finally:
        if owner.poll() is None:
            owner.kill()
        owner.communicate(timeout=5)


def test_healer_preserves_unreadable_ownership_metadata(tmp_path):
    from cochem_base.cochem_h5_healer import create_swmr_lock, force_release_swmr

    database = tmp_path / "invalid_metadata.h5"
    lock_path = create_swmr_lock(database)
    lock_path.write_text("interrupted metadata write", encoding="utf-8")
    result = force_release_swmr(database)
    assert result["lock_released"] is False
    assert lock_path.read_text(encoding="utf-8") == "interrupted metadata write"


@pytest.mark.parametrize("backend", ["canonical", "temporal"])
def test_pes_ingress_requires_explicit_convergence_and_preserves_unknown_time(tmp_path, backend):
    """Storage protocol values are not physical calibration/solver evidence."""
    if backend == "canonical":
        from cochem_base.core_engine.cochem_core_pes_store import PESStore
    else:
        from cochem_base.core_engine.cochem_temporal_router import PESStore

    path = tmp_path / f"{backend}.h5"
    store = PESStore(path)
    # Deliberately nonconverged protocol record: no successful scientific result is claimed.
    payload = {"coords": [[0.0, 0.0, 0.0]], "energies": [0.0]}
    original = path.read_bytes()
    for flag in (None, "True", 1, [True, False]):
        with pytest.raises(ValueError, match="convergence|Convergence"):
            store.add_points("storage_contract", **payload, converged=flag)
        assert path.read_bytes() == original
    store.add_points("storage_contract", **payload, converged=False)
    with h5py.File(path, "r") as handle:
        assert not handle["points/storage_contract/converged"][0]
        elapsed = handle["points/storage_contract/wall_s"]
        assert np.isnan(elapsed[0])
        assert "not measured" in elapsed.attrs["missing_value_policy"]
    assert len(store.dataset("storage_contract", converged_only=True)[1]) == 0
    if backend == "canonical":
        assert store.get_points("storage_contract")[0]["wall_s"] is None


def test_staged_results_require_boolean_evidence_before_creating_a_chunk(tmp_path):
    from cochem_base.concurrency.hdf5_coordinator import HDF5PersistenceCoordinator

    payload = {"method_id": "storage_contract", "coords": [[0.0, 0.0, 0.0]], "energies": [0.0]}
    for flag in (None, "False", 0, [False, False]):
        with pytest.raises(ValueError, match="convergence|Convergence"):
            HDF5PersistenceCoordinator.stage_chunk(tmp_path, **payload, converged=flag)
        assert not list(tmp_path.rglob("*.h5"))
    chunk = HDF5PersistenceCoordinator.stage_chunk(tmp_path, **payload, converged=False)
    with h5py.File(chunk, "r") as handle:
        assert not handle["points/storage_contract/converged"][0]
        assert np.isnan(handle["points/storage_contract/wall_s"][0])


def test_pes_record_defaults_do_not_claim_convergence_or_measured_elapsed_time():
    from pydantic import ValidationError
    from cochem_base.core.models import PESPointRecord

    record = PESPointRecord()
    assert record.converged is None
    assert record.wall_s is None
    assert json.loads(record.model_dump_json())["wall_s"] is None
    for invalid in ("true", 1):
        with pytest.raises(ValidationError):
            PESPointRecord(converged=invalid)
    for invalid in (-1.0, float("nan"), float("inf")):
        with pytest.raises(ValidationError):
            PESPointRecord(wall_s=invalid)


@pytest.mark.parametrize("held_mode", ["read", "write"])
def test_temporal_store_obeys_canonical_process_lock(tmp_path, held_mode):
    from cochem_base.core_engine.cochem_core_pes_store import ReadWriteFileLock
    from cochem_base.core_engine.cochem_temporal_router import PESStore

    store = PESStore(tmp_path / "temporal_shared.h5")
    assert store.lock_timeout == 10.0
    guard = ReadWriteFileLock(store.lock_path)
    held = guard.read_lock() if held_mode == "read" else guard.write_lock()
    with held:
        child = _child(
            """
import sys
from cochem_base.core_engine.cochem_temporal_router import PESStore
from cochem_base.exceptions import HDF5LockTimeoutError
try:
    PESStore(sys.argv[1], lock_timeout=0.15)
    raise AssertionError('Temporal store entered while another process owns a canonical lock')
except HDF5LockTimeoutError:
    print('blocked')
""", store.path,
        )
        assert child.stdout.strip() == "blocked"


def test_temporal_store_rejects_invalid_hessian_before_replacement(tmp_path):
    from cochem_base.core_engine.cochem_temporal_router import PESStore

    store = PESStore(tmp_path / "hessian_validation.h5")
    store.add_hessian("protocol_matrix", np.eye(3), level="HF", geometry_ref="storage_contract")
    with pytest.raises(ValueError, match="finite square"):
        store.add_hessian("protocol_matrix", [[float("nan")]], level="HF", geometry_ref="storage_contract")
    with h5py.File(store.path, "r") as handle:
        np.testing.assert_array_equal(handle["hessians/protocol_matrix"][:], np.eye(3))
