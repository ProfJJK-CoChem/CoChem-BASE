"""Concurrent archive replay of retained ORCA observations, not new chemistry."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import h5py
import numpy as np
import pytest

from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager
from cochem_base.core_engine.gradient_telemetry import ORCAGradientStream
from cochem_base.core_engine.scientific_telemetry import append_scientific_result, read_scientific_results
from cochem_base.core_engine.scientific_writer import scientific_writer_scope


@pytest.fixture
def native_records(tmp_path):
    source = Path(__file__).parents[1] / "data/orca_6_1_1_water_hf_sto3g"
    provenance = json.loads((source / "provenance.json").read_bytes())
    original = source / "water.out.txt"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == provenance["files"][original.name]["sha256"]
    store = tmp_path / "source-records.h5"
    stream = ORCAGradientStream("water", ["O", "H", "H"], source_id=provenance["files"][original.name]["sha256"],
                                store_path=store)
    for line in original.read_text().splitlines():
        stream(line)
    stream.finish()
    measured = read_scientific_results("water", store_path=store)
    assert measured["gradients_hartree_per_bohr"].shape == (5, 3, 3)
    return measured


def publish(store, measured, index, job="water"):
    native = index % len(measured["energy_hartree"])
    append_scientific_result(job, measured["nuclides"], measured["coordinates_angstrom"][native],
        measured["energy_hartree"][native], gradients=measured["gradients_hartree_per_bohr"][native],
        metadata={"scope": "retained native ORCA observation replay for I/O validation", "replay_index": index,
                  "native_observation_index": native}, store_path=store)


def verify_snapshot(snapshot, measured):
    count = len(snapshot["energy_hartree"])
    assert len(snapshot["coordinates_angstrom"]) == count == len(snapshot["metadata"])
    assert snapshot["gradients_hartree_per_bohr"].shape == (count, 3, 3)
    np.testing.assert_array_equal(snapshot["gradient_record_indices"], np.arange(count))
    for index, metadata in enumerate(snapshot["metadata"]):
        native = metadata["native_observation_index"]
        assert snapshot["energy_hartree"][index] == measured["energy_hartree"][native]
        np.testing.assert_array_equal(snapshot["coordinates_angstrom"][index], measured["coordinates_angstrom"][native])
        np.testing.assert_array_equal(snapshot["gradients_hartree_per_bohr"][index], measured["gradients_hartree_per_bohr"][native])


@pytest.mark.parametrize("persistent", [False, True])
def test_actual_scientific_api_writer_and_three_snapshot_threads_coexist(tmp_path, native_records, persistent):
    from contextlib import nullcontext
    store = tmp_path / "threaded.h5"
    barrier = threading.Barrier(4)
    done = threading.Event()
    counts = []
    with scientific_writer_scope(store_path=store) if persistent else nullcontext():
        publish(store, native_records, 0)
        def reader():
            barrier.wait(timeout=10)
            reads = 0
            while not done.is_set() or reads < 20:
                verify_snapshot(read_scientific_results("water", store_path=store), native_records)
                reads += 1
            return reads
        with ThreadPoolExecutor(max_workers=3) as pool:
            readers = [pool.submit(reader) for _ in range(3)]
            try:
                barrier.wait(timeout=10)
                for index in range(1, 40):
                    publish(store, native_records, index)
            finally:
                done.set()
            counts = [future.result(timeout=20) for future in readers]
        assert min(counts) >= 20
    final = read_scientific_results("water", store_path=store)
    assert len(final["energy_hartree"]) == 40
    verify_snapshot(final, native_records)
    # The standalone API and explicit scope both actually release the write
    # handle; a subsequent ordinary read/write-open is not a hidden SWMR lease.
    with h5py.File(store, "r+", libver="latest") as reopened:
        assert reopened.swmr_mode is False


def test_persistent_readers_open_before_each_next_append_observe_native_records(tmp_path, native_records):
    store = tmp_path / "persistent-readers.h5"
    with scientific_writer_scope(store_path=store):
        publish(store, native_records, 0)
        manager = CoChemHDF5Manager(h5_path=store)
        with manager.swmr_reader() as reader:
            for index in range(1, 12):
                publish(store, native_records, index)
                reader["trajectories/water/committed_records"].refresh()
                reader["trajectories/water/energy_hartree"].refresh()
                assert int(reader["trajectories/water/committed_records"][()]) == index + 1
                assert reader["trajectories/water/energy_hartree"][index] == native_records["energy_hartree"][index % 5]
                verify_snapshot(read_scientific_results("water", store_path=store), native_records)


def test_three_independent_process_readers_coexist_with_persistent_production_writer(tmp_path, native_records):
    store = tmp_path / "process-readers.h5"
    program = """
import json,sys
from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager
from cochem_base.core_engine.scientific_telemetry import read_scientific_results
manager=CoChemHDF5Manager(h5_path=sys.argv[1])
with manager.swmr_reader() as live:
    print('ready',flush=True)
    for command in sys.stdin:
        if command.strip()=='stop':break
        live['trajectories/water/committed_records'].refresh()
        snapshot=read_scientific_results('water',store_path=sys.argv[1])
        print(json.dumps({'count':len(snapshot['energy_hartree']),'energy':snapshot['energy_hartree'].tolist(),
            'coordinates':snapshot['coordinates_angstrom'].tolist(),'gradients':snapshot['gradients_hartree_per_bohr'].tolist(),
            'indices':snapshot['gradient_record_indices'].tolist(),'metadata':snapshot['metadata']}),flush=True)
"""
    readers = []
    with scientific_writer_scope(store_path=store):
        publish(store, native_records, 0)
        with ThreadPoolExecutor(max_workers=3) as pool:
            try:
                for _ in range(3):
                    readers.append(subprocess.Popen([sys.executable, "-u", "-c", program, str(store)],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        env=os.environ.copy()))
                for future in [pool.submit(reader.stdout.readline) for reader in readers]:
                    assert future.result(timeout=20).strip() == "ready"
                for index in range(1, 10):
                    publish(store, native_records, index)
                    for reader in readers:
                        reader.stdin.write("snapshot\n")
                        reader.stdin.flush()
                    for future in [pool.submit(reader.stdout.readline) for reader in readers]:
                        observed = json.loads(future.result(timeout=10))
                        assert observed["count"] == index + 1
                        verify_snapshot({"energy_hartree": np.asarray(observed["energy"]),
                            "coordinates_angstrom": np.asarray(observed["coordinates"]),
                            "gradients_hartree_per_bohr": np.asarray(observed["gradients"]),
                            "gradient_record_indices": np.asarray(observed["indices"]),
                            "metadata": observed["metadata"]}, native_records)
                for reader in readers:
                    reader.stdin.write("stop\n")
                    reader.stdin.flush()
                    assert reader.wait(timeout=10) == 0, reader.stderr.read()
            finally:
                for reader in readers:
                    if reader.poll() is None:
                        reader.kill()
                    reader.communicate(timeout=5)


def test_new_job_topology_is_registered_between_short_snapshots(tmp_path, native_records):
    store = tmp_path / "two-jobs.h5"
    done = threading.Event()
    with scientific_writer_scope(store_path=store):
        publish(store, native_records, 0)
        def follow():
            reads = 0
            while not done.is_set() or reads < 10:
                verify_snapshot(read_scientific_results("water", store_path=store), native_records)
                reads += 1
            return reads
        with ThreadPoolExecutor(max_workers=2) as pool:
            readers = [pool.submit(follow) for _ in range(2)]
            try:
                publish(store, native_records, 0, job="second")
                publish(store, native_records, 1)
                publish(store, native_records, 1, job="second")
            finally:
                done.set()
            assert all(future.result(timeout=10) >= 10 for future in readers)
        for job in ("water", "second"):
            verify_snapshot(read_scientific_results(job, store_path=store), native_records)


def test_real_uncommitted_gradient_buffer_is_excluded_and_next_append_recovers(tmp_path, native_records):
    store = tmp_path / "interrupted.h5"
    publish(store, native_records, 0)
    manager = CoChemHDF5Manager(h5_path=store)
    with manager.transaction("a") as archive:
        gradients = archive["trajectories/water/gradients_hartree_per_bohr"]
        gradients.resize(3, axis=0)
        gradients[1:3] = native_records["gradients_hartree_per_bohr"][1:3]
        # An actual resize can become durable before assignment. Its default
        # zero index is an uncommitted tail, never another gradient for row0.
        archive["trajectories/water/gradient_record_indices"].resize(2, axis=0)
        archive.flush()
    snapshot = read_scientific_results("water", store_path=store)
    assert len(snapshot["energy_hartree"]) == 1
    verify_snapshot(snapshot, native_records)
    publish(store, native_records, 1)
    snapshot = read_scientific_results("water", store_path=store)
    assert len(snapshot["energy_hartree"]) == 2
    verify_snapshot(snapshot, native_records)


def test_writer_exception_scope_releases_physical_file_before_return(tmp_path, native_records):
    store = tmp_path / "closed-after-exception.h5"
    with pytest.raises(RuntimeError, match="producer failure"):
        with scientific_writer_scope(store_path=store):
            publish(store, native_records, 0)
            raise RuntimeError("Retained observation replay producer failure")
    with h5py.File(store, "r+", libver="latest") as archive:
        assert archive.swmr_mode is False
    verify_snapshot(read_scientific_results("water", store_path=store), native_records)


def test_missing_committed_gradient_is_rejected_instead_of_filled_with_zero(tmp_path, native_records):
    store = tmp_path / "missing-gradient.h5"
    publish(store, native_records, 0)
    manager = CoChemHDF5Manager(h5_path=store)
    with manager.transaction("a") as archive:
        archive["trajectories/water/gradients_hartree_per_bohr"].resize(0, axis=0)
    with pytest.raises(ValueError, match="gradients are incomplete"):
        read_scientific_results("water", store_path=store)
    with pytest.raises(ValueError, match="indices or observations are invalid"):
        publish(store, native_records, 1)
    with h5py.File(store, "r", libver="latest", swmr=True) as archive:
        assert archive["trajectories/water/gradients_hartree_per_bohr"].shape[0] == 0
        assert int(archive["trajectories/water/committed_records"][()]) == 1


@pytest.mark.parametrize("helper", ["telemetry", "preview"])
def test_gui_reader_helpers_in_three_processes_read_actual_native_rows_during_writer_scope(tmp_path, native_records, helper):
    """Real GUI helpers read while the physical producer writer lock is held."""
    store = tmp_path / (helper + "-gui-readers.h5")
    program = """
import json,sys
from cochem_base.core.cochem_core_hdf5_manager import CoChemHDF5Manager
from cochem_base.spectroscopy.parser import read_hdf5_swmr_telemetry,read_hdf5_dataset_previews
manager=CoChemHDF5Manager(h5_path=sys.argv[1])
with manager.swmr_reader() as live:
    print('ready',flush=True)
    for command in sys.stdin:
        if command.strip()=='stop':break
        if sys.argv[2]=='telemetry':
            raw=read_hdf5_swmr_telemetry(sys.argv[1])['trajectories']['water']
        else:
            rows=read_hdf5_dataset_previews(sys.argv[1])
            raw={row['name'].rsplit('/',1)[-1]:row['values'] for row in rows if row['name'].startswith('trajectories/water/')}
        print(json.dumps({'count':int(raw['committed_records']),'energy':raw['energy_hartree'].tolist(),
            'coordinates':raw['coordinates_angstrom'].tolist(),'gradients':raw['gradients_hartree_per_bohr'].tolist(),
            'indices':raw['gradient_record_indices'].tolist(),
            'metadata':[json.loads(value.decode('utf-8')) for value in raw['metadata_json']]}),flush=True)
"""
    readers = []
    with scientific_writer_scope(store_path=store):
        publish(store, native_records, 0)
        with ThreadPoolExecutor(max_workers=3) as pool:
            try:
                for _ in range(3):
                    readers.append(subprocess.Popen([sys.executable, "-u", "-c", program, str(store), helper],
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        env=os.environ.copy()))
                for future in [pool.submit(reader.stdout.readline) for reader in readers]:
                    assert future.result(timeout=20).strip() == "ready"
                for index in range(1, 20):
                    publish(store, native_records, index)
                    for reader in readers:
                        reader.stdin.write("snapshot\n")
                        reader.stdin.flush()
                    for future in [pool.submit(reader.stdout.readline) for reader in readers]:
                        observed = json.loads(future.result(timeout=15))
                        assert observed["count"] == index + 1
                        verify_snapshot({"energy_hartree": np.asarray(observed["energy"]),
                            "coordinates_angstrom": np.asarray(observed["coordinates"]),
                            "gradients_hartree_per_bohr": np.asarray(observed["gradients"]),
                            "gradient_record_indices": np.asarray(observed["indices"]),
                            "metadata": observed["metadata"]}, native_records)
                for reader in readers:
                    reader.stdin.write("stop\n")
                    reader.stdin.flush()
                    assert reader.wait(timeout=10) == 0, reader.stderr.read()
            finally:
                for reader in readers:
                    if reader.poll() is None:
                        reader.kill()
                    reader.communicate(timeout=5)


def test_gui_reader_helpers_exclude_real_uncommitted_buffers_and_reject_lost_committed_data(tmp_path, native_records):
    from cochem_base.spectroscopy.parser import read_hdf5_swmr_telemetry, read_hdf5_dataset_previews
    store = tmp_path / "gui-interrupted.h5"
    publish(store, native_records, 0)
    manager = CoChemHDF5Manager(h5_path=store)
    with manager.transaction("a") as archive:
        group = archive["trajectories/water"]
        for name in ("coordinates_angstrom", "energy_hartree", "metadata_json", "gradients_hartree_per_bohr", "gradient_record_indices"):
            group[name].resize(3, axis=0)
        group["coordinates_angstrom"][1:3] = native_records["coordinates_angstrom"][1:3]
        group["energy_hartree"][1:3] = native_records["energy_hartree"][1:3]
        group["gradients_hartree_per_bohr"][1:3] = native_records["gradients_hartree_per_bohr"][1:3]
        archive.flush()
    rows = {row["name"]: row for row in read_hdf5_dataset_previews(store)}
    assert rows["trajectories/water/coordinates_angstrom"]["shape"] == (1, 3, 3)
    assert rows["trajectories/water/coordinates_angstrom"]["stored_shape"] == (3, 3, 3)
    assert rows["trajectories/water/gradients_hartree_per_bohr"]["total"] == 9
    raw = read_hdf5_swmr_telemetry(store)["trajectories"]["water"]
    assert int(raw["committed_records"]) == 1
    np.testing.assert_array_equal(raw["energy_hartree"], native_records["energy_hartree"][:1])
    np.testing.assert_array_equal(raw["gradients_hartree_per_bohr"], native_records["gradients_hartree_per_bohr"][:1])
    with manager.transaction("a") as archive:
        archive["trajectories/water/gradients_hartree_per_bohr"].resize(0, axis=0)
    for helper in (read_hdf5_swmr_telemetry, read_hdf5_dataset_previews):
        with pytest.raises(ValueError, match="gradients are incomplete"):
            helper(store)

# Proposed additions to tests/base/test_scientific_swmr_lifecycle.py.
# Uses its genuine native_records, publish and verify_snapshot helpers.

@pytest.mark.parametrize("api", ["canonical", "gui-telemetry", "gui-preview"])
@pytest.mark.parametrize("closing", [True, False])
def test_admitted_nested_reader_finishes_during_actual_writer_transition(tmp_path, native_records, api, closing):
    """An admitted reader can finish; an independent new reader waits."""
    import time
    from cochem_base.core_engine.scientific_writer import _store, scientific_reader_snapshot
    from cochem_base.spectroscopy.parser import read_hdf5_swmr_telemetry, read_hdf5_dataset_previews
    store = tmp_path / "nested-transition.h5"
    ready, admitted, transition_requested, new_attempted = (threading.Event() for _ in range(4))
    new_entered = threading.Event()
    def real_read():
        if api == "canonical":
            view = read_scientific_results("water", store_path=store)
            return view["energy_hartree"], view["coordinates_angstrom"], view["gradients_hartree_per_bohr"]
        if api == "gui-telemetry":
            view = read_hdf5_swmr_telemetry(store)["trajectories"]["water"]
        else:
            view = {row["name"].rsplit("/", 1)[-1]: row["values"]
                    for row in read_hdf5_dataset_previews(store)
                    if row["name"].startswith("trajectories/water/")}
        return view["energy_hartree"], view["coordinates_angstrom"], view["gradients_hartree_per_bohr"]

    def producer():
        with scientific_writer_scope(store_path=store):
            publish(store, native_records, 0)
            ready.set()
            assert transition_requested.wait(10)
            if not closing:
                # A different real job creates new topology before reactivation.
                publish(store, native_records, 1, job="second")

    def existing_reader():
        assert ready.wait(10)
        with scientific_reader_snapshot(store_path=store):
            admitted.set()
            shared = _store(store)
            deadline = time.monotonic() + 5
            while True:
                with shared.condition:
                    waiting = shared.transition and shared.closing is closing
                    assert shared.readers >= 1
                if waiting:
                    break
                assert time.monotonic() < deadline, "Actual writer never entered the requested transition"
                time.sleep(.001)
            assert new_attempted.wait(5)
            # Observe both the real topology waiter and the independently
            # blocked snapshot waiter; an event alone does not prove admission.
            deadline = time.monotonic() + 5
            while True:
                with shared.condition:
                    blocked = len(shared.condition._waiters) >= 2
                    assert shared.transition and shared.readers == 1
                if blocked:
                    break
                assert time.monotonic() < deadline, "New reader never actually waited for the transition"
                time.sleep(.001)
            energies, coordinates, gradients = real_read()
            np.testing.assert_array_equal(energies, native_records["energy_hartree"][:1])
            np.testing.assert_array_equal(coordinates, native_records["coordinates_angstrom"][:1])
            np.testing.assert_array_equal(gradients, native_records["gradients_hartree_per_bohr"][:1])
            assert not new_entered.is_set()
            with shared.condition:
                assert shared.readers == 1
            # An actual absent-job error is caught inside the outer snapshot.
            # A subsequent nested read must still use that admitted scope.
            with pytest.raises(KeyError):
                read_scientific_results("absent-native-job", store_path=store)
            real_read()

    def new_reader():
        assert admitted.wait(10)
        shared = _store(store)
        deadline = time.monotonic() + 5
        while True:
            with shared.condition:
                waiting = shared.transition and shared.closing is closing
            if waiting:
                break
            assert time.monotonic() < deadline
            time.sleep(.001)
        new_attempted.set()
        with scientific_reader_snapshot(store_path=store):
            new_entered.set()
            with shared.condition:
                # A later producer close may begin after this admission. It
                # must wait for this admitted reader, which can still finish.
                assert shared.readers == 1
            verify_snapshot(read_scientific_results("water", store_path=store), native_records)

    with ThreadPoolExecutor(max_workers=3) as pool:
        writer = pool.submit(producer)
        first = pool.submit(existing_reader)
        assert admitted.wait(10)
        follower = pool.submit(new_reader)
        transition_requested.set()
        first.result(timeout=15)
        writer.result(timeout=15)
        follower.result(timeout=15)
    assert new_entered.is_set()
    verify_snapshot(read_scientific_results("water", store_path=store), native_records)
    if not closing:
        second = read_scientific_results("second", store_path=store)
        assert second["metadata"][0]["native_observation_index"] == 1
        np.testing.assert_array_equal(second["gradients_hartree_per_bohr"], native_records["gradients_hartree_per_bohr"][1:2])
    with h5py.File(store, "r+", libver="latest") as reopened:
        assert not reopened.swmr_mode


def test_nested_reader_exception_resets_depth_and_later_native_append_succeeds(tmp_path, native_records):
    from cochem_base.core_engine.scientific_writer import _store, scientific_reader_snapshot
    from cochem_base.spectroscopy.parser import read_hdf5_swmr_telemetry
    store = tmp_path / "reader-exception.h5"
    publish(store, native_records, 0)
    with pytest.raises(KeyError):
        with scientific_reader_snapshot(store_path=store):
            read_hdf5_swmr_telemetry(store)  # actual depth >= 3 via preview helper
            read_scientific_results("absent-native-job", store_path=store)
    shared = _store(store)
    assert getattr(shared.reader_depth, "value", 0) == 0
    with shared.condition:
        assert shared.readers == 0 and shared.users == 0
    publish(store, native_records, 1)
    verify_snapshot(read_scientific_results("water", store_path=store), native_records)


@pytest.mark.parametrize("mode", ["public-append", "existing-handle"])
def test_reader_to_writer_conflict_is_typed_prompt_and_preserves_native_store(tmp_path, native_records, mode):
    """A bounded isolated worker prevents a regressed self-deadlock hanging CI."""
    program = r'''
from pathlib import Path
import hashlib,sys,time
import numpy as np
from cochem_base.core_engine.scientific_telemetry import append_scientific_result,read_scientific_results
from cochem_base.core_engine.scientific_writer import scientific_writer_scope,scientific_reader_snapshot,ScientificSnapshotConflictError
source,store,mode=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
actual=read_scientific_results('water',store_path=source)
assert actual['gradients_hartree_per_bohr'].shape==(5,3,3)
def publish(path,index):
    append_scientific_result('water',actual['nuclides'],actual['coordinates_angstrom'][index],actual['energy_hartree'][index],gradients=actual['gradients_hartree_per_bohr'][index],metadata={'scope':'retained native ORCA I/O replay','native_observation_index':index},store_path=path)
def forbidden_initialize(manager):raise AssertionError('A forbidden operation reached initialization')
def forbidden_append(manager,writer):raise AssertionError('A forbidden operation reached the writer callback')
with scientific_writer_scope(store_path=store) as writer:
    publish(store,0)
    with scientific_reader_snapshot(store_path=store):
        observed=read_scientific_results('water',store_path=store)
        np.testing.assert_array_equal(observed['energy_hartree'],actual['energy_hartree'][:1])
        np.testing.assert_array_equal(observed['coordinates_angstrom'],actual['coordinates_angstrom'][:1])
        np.testing.assert_array_equal(observed['gradients_hartree_per_bohr'],actual['gradients_hartree_per_bohr'][:1])
        before=hashlib.sha256(store.read_bytes()).hexdigest()
        state=(writer.users,writer.readers,writer.commands.qsize())
        started=time.monotonic()
        try:
            if mode=='public-append':publish(store,1)
            else:writer.write('trajectories/water',forbidden_initialize,forbidden_append)
        except ScientificSnapshotConflictError:pass
        else:raise AssertionError('Scientific reader-to-writer conflict was not refused')
        assert time.monotonic()-started<1
        assert (writer.users,writer.readers,writer.commands.qsize())==state
        assert hashlib.sha256(store.read_bytes()).hexdigest()==before
        other=store.with_name('independent-store.h5')
        publish(other,0)
        assert read_scientific_results('water',store_path=other)['energy_hartree'][0]==actual['energy_hartree'][0]
    publish(store,1)
assert len(read_scientific_results('water',store_path=store)['energy_hartree'])==2
'''
    completed = subprocess.run([sys.executable, "-c", program, str(tmp_path / "source-records.h5"),
        str(tmp_path / "guarded-store.h5"), mode], capture_output=True, text=True, timeout=12,
        env=os.environ.copy())
    assert completed.returncode == 0, completed.stderr
    verify_snapshot(read_scientific_results("water", store_path=tmp_path / "guarded-store.h5"), native_records)
