"""
Storage and process integration tests for CoChem Core HDF5 Manager and Distributed IPC.

Verifies:
1. Chunk 17 REQ-BASE-003: Live SWMR telemetry on supported filesystems.
2. Real-Time IPC: Local scratch SQLite WAL queue and ZeroMQ streaming.
3. Single Master Node Enforcement: Strict gatekeeping delegating HDF5 writes to Rank 0 / Master.
4. Rigorous HDF5 Filtering: Mandatory gzip+shuffle+fletcher32 filters on all serialized datasets.
5. QCSchema Compliance: Full validation and lossless round-trip serialization of QCSchema v1/v2 records.
6. VRAM Offloading & Tensor Stripping: Automatic detachment and conversion of PyTorch/JAX tensors to NumPy/Python scalars on host RAM.
7. Landscape Database Management: Basin and calculation storage in landscape.h5 with atomic locking.

Zero-Mock Policy: 100% genuine OS processes, genuine filelocks, genuine SQLite WAL, and real HDF5 operations.
Hand-entered scientific records below are serialization fixtures; they are not
measured engine outputs or evidence of a quantum method's numerical accuracy.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import h5py
import numpy as np
import pytest
from pydantic import ValidationError

try:
    import torch
except ImportError:
    torch = None

try:
    import jax
    import jax.numpy as jnp
except ImportError:
    jax = None
    jnp = None

try:
    import qcelemental as qcel
    try:
        from qcelemental.models.v2 import AtomicResult as QCElAtomicResult
        from qcelemental.models.v2 import Molecule as QCElMolecule
    except (ImportError, RuntimeError):
        from qcelemental.models import AtomicResult as QCElAtomicResult  # type: ignore
        from qcelemental.models import Molecule as QCElMolecule  # type: ignore
except ImportError:
    qcel = None
    QCElAtomicResult = None
    QCElMolecule = None

from cochem_base.core.cochem_core_hdf5_manager import (
    BasinRecord,
    CoChemHDF5Manager,
    HDF5FilterViolationError,
    HDF5ManagerError,
    MasterDataAggregator,
    MasterWriteGatekeeper,
    NonMasterWriteRejectionError,
    QCSchemaAtomicResult,
    QCSchemaDriver,
    QCSchemaModel,
    QCSchemaMolecule,
    QCSchemaOptimizationResult,
    QCSchemaProperties,
    QCSchemaWavefunction,
    SQLiteWALQueue,
    ZMQRealTimeStreamer,
    is_master_node,
    resolve_landscape_h5_path,
    sanitize_for_host_ram,
    strip_tensor_to_numpy,
    verify_dataset_filters,
    verify_no_swmr_usage,
    write_dataset_filtered,
)


def _run_storage_process(
    source: str,
    *arguments: object,
    environment: dict[str, str] | None = None,
    preserve_slurm: bool = False,
) -> None:
    """Run the real storage implementation in an independently configured process."""
    child_environment = os.environ.copy()
    for name in (
        "COCHEM_IS_MASTER", "OMPI_COMM_WORLD_RANK", "PMI_RANK", "RANK",
        "MV2_COMM_WORLD_RANK",
    ):
        child_environment.pop(name, None)
    if not preserve_slurm:
        child_environment.pop("SLURM_PROCID", None)
    child_environment.update(environment or {})
    completed = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source), *(str(arg) for arg in arguments)],
        env=child_environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def _qcschema_serialization_payloads() -> tuple[dict[str, Any], dict[str, Any]]:
    """Minimal schema examples; values are not attributed to an executed engine."""
    molecule = {"symbols": ["He"], "geometry": [0.0, 0.0, 0.0]}
    atomic = {
        "molecule": molecule,
        "driver": "energy",
        "model": {"method": "serialization_fixture"},
        "return_result": -1.0,
        "provenance": {"creator": "serialization_fixture", "physical_reference": False},
        "success": False,
    }
    optimization = {
        "initial_molecule": molecule,
        "final_molecule": molecule,
        "trajectory": [atomic.copy()],
        "energies": [-1.0],
        "provenance": {"creator": "serialization_fixture", "physical_reference": False},
        "success": False,
    }
    return atomic, optimization


def test_qcschema_models_require_explicit_boolean_success() -> None:
    atomic, optimization = _qcschema_serialization_payloads()
    for model, payload in (
        (QCSchemaAtomicResult, atomic),
        (QCSchemaOptimizationResult, optimization),
    ):
        del payload["success"]
        with pytest.raises(ValidationError, match="success"):
            model.model_validate(payload)
        for invalid_status in (None, "false", 1):
            with pytest.raises(ValidationError, match="success"):
                model.model_validate({**payload, "success": invalid_status})


@pytest.mark.parametrize("record_format", ["atomic_v1", "atomic_v2", "optimization"])
@pytest.mark.parametrize("status_case", ["missing", "null", "string", "integer"])
def test_qcschema_ingestion_rejects_unreported_or_coerced_success(
    tmp_path: Path, record_format: str, status_case: str,
) -> None:
    atomic, optimization = _qcschema_serialization_payloads()
    payload = optimization if record_format == "optimization" else atomic
    if record_format == "atomic_v2":
        payload["input_data"] = {
            "specification": {"driver": payload.pop("driver"), "model": payload.pop("model")},
        }
    del payload["success"]
    if status_case != "missing":
        payload["success"] = {"null": None, "string": "false", "integer": 1}[status_case]
    path = tmp_path / "unreported.h5"
    manager = CoChemHDF5Manager(h5_path=path)
    write = (
        manager.write_qcschema_optimization_result
        if record_format == "optimization" else manager.write_qcschema_result
    )
    with pytest.raises(ValidationError, match="success"):
        write("unreported", payload)
    # A rejected status must not publish a calculation or trajectory record.
    if path.exists():
        with h5py.File(path, "r") as archive:
            assert "calculations/unreported" not in archive
            assert "trajectories/unreported" not in archive


@pytest.mark.parametrize("location", ["atomic", "optimization", "step"])
@pytest.mark.parametrize("status_case", ["missing", "string", "integer"])
def test_qcschema_archive_rejects_unreported_or_corrupt_success(
    tmp_path: Path, location: str, status_case: str,
) -> None:
    atomic, optimization = _qcschema_serialization_payloads()
    path = tmp_path / "archive.h5"
    manager = CoChemHDF5Manager(h5_path=path)
    manager.write_qcschema_result("atomic", atomic)
    manager.write_qcschema_optimization_result("optimization", optimization)
    assert manager.read_qcschema_result("atomic").success is False
    loaded = manager.read_qcschema_optimization_result("optimization")
    assert loaded.success is False
    assert loaded.trajectory[0].success is False
    with h5py.File(path, "a") as archive:
        if location == "atomic":
            group = archive["calculations/atomic"]
        elif location == "optimization":
            group = archive["trajectories/optimization"]
        else:
            trajectory = archive["trajectories/optimization/steps"]
            group = trajectory[next(iter(trajectory))]
        del group.attrs["success"]
        if status_case != "missing":
            group.attrs["success"] = "false" if status_case == "string" else 1
    read = (
        manager.read_qcschema_result
        if location == "atomic" else manager.read_qcschema_optimization_result
    )
    with pytest.raises(ValidationError, match="success"):
        read("atomic" if location == "atomic" else "optimization")

# =============================================================================
# 1. SWMR TELEMETRY AND LEGACY ARCHIVE COMPATIBILITY
# =============================================================================

def test_chunk17_swmr_reader_observes_flushed_energy(tmp_path: Path) -> None:
    """Chunk 17 supersedes the legacy blanket SWMR source-code prohibition."""
    mgr = CoChemHDF5Manager(h5_path=tmp_path / "complexes.h5")
    mgr.init_swmr_dataset("energies", (0,), (None,), (32,))
    with mgr.swmr_writer() as writer:
        assert writer.swmr_mode
        with mgr.swmr_reader() as reader:
            assert reader.swmr_mode
            mgr.append_swmr_chunk("energies", np.array([-76.4]), writer_file=writer)
            np.testing.assert_array_equal(
                mgr.read_swmr_dataset("energies", reader_file=reader), [-76.4]
            )


def test_completed_archive_supports_standard_reader(tmp_path: Path) -> None:
    """A closed archive remains readable by ordinary HDF5 clients."""
    h5_path = tmp_path / "test_no_swmr.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_path)

    # Write a test record
    mgr.write_basin_record("basin_01", BasinRecord(molecule_name="water", energy=-76.4, symmetry_group="C2v"))

    # Open and verify flags
    with h5py.File(h5_path, "r") as f:
        assert not getattr(f, "swmr_mode", False)


# =============================================================================
# 2. VRAM OFFLOADING & TENSOR STRIPPING
# =============================================================================

def test_strip_tensor_to_numpy_scalars_and_arrays() -> None:
    """Tests that PyTorch and JAX tensors are stripped to host RAM NumPy arrays and Python scalars."""
    # NumPy arrays and Python primitives
    arr = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    assert np.array_equal(strip_tensor_to_numpy(arr), arr)
    assert strip_tensor_to_numpy(42.0) == 42.0
    assert strip_tensor_to_numpy(10) == 10
    assert strip_tensor_to_numpy("benzene") == "benzene"

    # PyTorch Tensors with autograd computation graph
    if torch is not None:
        t_scalar = torch.tensor(3.14159, requires_grad=True)
        stripped_scalar = strip_tensor_to_numpy(t_scalar)
        assert isinstance(stripped_scalar, (float, np.floating))
        assert abs(float(stripped_scalar) - 3.14159) < 1e-5

        t_tensor = torch.tensor([[1.0, 2.0], [3.0, 4.0]], requires_grad=True)
        out = (t_tensor ** 2).sum()
        out.backward()
        assert t_tensor.grad is not None

        stripped_tensor = strip_tensor_to_numpy(t_tensor)
        assert isinstance(stripped_tensor, np.ndarray)
        assert not hasattr(stripped_tensor, "grad_fn")
        assert stripped_tensor.flags.c_contiguous
        assert np.allclose(stripped_tensor, [[1.0, 2.0], [3.0, 4.0]])

    # JAX Arrays
    if jax is not None and jnp is not None:
        j_arr = jnp.array([5.0, 6.0, 7.0])
        stripped_jax = strip_tensor_to_numpy(j_arr)
        assert isinstance(stripped_jax, np.ndarray)
        assert np.allclose(stripped_jax, [5.0, 6.0, 7.0])


def test_sanitize_for_host_ram_nested_structures() -> None:
    """Tests recursive sanitization of complex nested structures containing tensors."""
    payload: Dict[str, Any] = {
        "molecule": "ethanol",
        "energy": 42.5,
        "tags": ["mlff", "dft"],
        "metadata": {
            "step": 1,
            "raw_coords": np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]]),
        }
    }

    if torch is not None:
        payload["forces"] = torch.tensor([[0.1, -0.2, 0.0], [0.0, 0.05, -0.1]], requires_grad=True)
        payload["tensor_scalar"] = torch.tensor(1.234)

    sanitized = sanitize_for_host_ram(payload)
    assert isinstance(sanitized, dict)
    assert sanitized["molecule"] == "ethanol"
    assert isinstance(sanitized["metadata"]["raw_coords"], np.ndarray)

    if torch is not None:
        assert isinstance(sanitized["forces"], np.ndarray)
        assert not hasattr(sanitized["forces"], "requires_grad")
        assert isinstance(sanitized["tensor_scalar"], (float, np.floating))


# =============================================================================
# 3. REAL-TIME IPC: SQLITE WAL ON LOCAL SCRATCH
# =============================================================================

def test_sqlite_wal_queue_lifecycle(tmp_path: Path) -> None:
    """Tests high-throughput real-time IPC queue using SQLite in WAL mode."""
    db_path = tmp_path / "scratch_ipc.db"
    queue = SQLiteWALQueue(db_path=db_path)

    # Verify WAL mode is active
    mode = queue.get_journal_mode()
    assert mode.upper() == "WAL", f"Journal mode must be WAL, got {mode}"

    # Push records
    r1_id = queue.push("wavefunction_stream", {"calc_id": "c1", "density": [1.0, 2.0, 3.0]}, sender="rank_1")
    r2_id = queue.push("wavefunction_stream", {"calc_id": "c2", "density": [4.0, 5.0, 6.0]}, sender="rank_2")
    r3_id = queue.push("telemetry", {"heartbeat": time.time()}, sender="rank_1")

    assert r1_id > 0
    assert r2_id > r1_id
    assert r3_id > r2_id
    assert queue.count_pending() == 3

    # Pop records for specific topic
    wf_records = queue.pop_pending(topic="wavefunction_stream", limit=10)
    assert len(wf_records) == 2
    assert wf_records[0]["payload"]["calc_id"] == "c1"
    assert wf_records[1]["payload"]["calc_id"] == "c2"
    assert queue.count_pending() == 1

    # Drain remaining
    all_rem = queue.drain_all()
    assert len(all_rem) == 1
    assert all_rem[0]["topic"] == "telemetry"
    assert queue.count_pending() == 0


def test_sqlite_wal_concurrency(tmp_path: Path) -> None:
    """Tests multi-threaded concurrent writers and reader in SQLite WAL mode."""
    db_path = tmp_path / "concurrent_wal.db"
    queue = SQLiteWALQueue(db_path=db_path)

    num_threads = 4
    records_per_thread = 25

    def worker(worker_id: int) -> None:
        q = SQLiteWALQueue(db_path=db_path)
        for i in range(records_per_thread):
            q.push("concurrency_topic", {"worker": worker_id, "seq": i}, sender=f"worker_{worker_id}")
            time.sleep(0.001)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    total_count = queue.count_pending()
    assert total_count == num_threads * records_per_thread

    drained = queue.drain_all()
    assert len(drained) == num_threads * records_per_thread


# =============================================================================
# 4. REAL-TIME IPC: ZEROMQ STREAMING
# =============================================================================

def test_zeromq_realtime_streamer_push_pull() -> None:
    """Tests low-latency ZeroMQ real-time streaming with multipart binary arrays."""
    ready_event = threading.Event()
    received_records: List[Dict[str, Any]] = []

    def server_consumer() -> None:
        receiver = ZMQRealTimeStreamer(host="127.0.0.1", port=5581)
        receiver.bind_pull(ready_event=ready_event)
        try:
            for _ in range(2):
                msg = receiver.recv_record(timeout_ms=4000)
                if msg is not None:
                    received_records.append(msg)
        finally:
            receiver.close()

    server_thread = threading.Thread(target=server_consumer)
    server_thread.start()

    assert ready_event.wait(timeout=3.0)
    time.sleep(0.1)

    client = ZMQRealTimeStreamer(host="127.0.0.1", port=5581)
    client.connect_push()
    try:
        client.send_record(
            topic="tensor_stream",
            metadata={"calc_id": "c_zmq_1", "step": 10},
            array=np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64),
        )
        client.send_record(
            topic="tensor_stream",
            metadata={"calc_id": "c_zmq_2", "step": 11},
            array=np.array([5.0, 6.0, 7.0], dtype=np.float64),
        )
        time.sleep(0.1)
    finally:
        client.close()

    server_thread.join(timeout=4.0)

    assert len(received_records) == 2
    assert received_records[0]["metadata"]["calc_id"] == "c_zmq_1"
    assert np.allclose(received_records[0]["array"], [[1.0, 2.0], [3.0, 4.0]])
    assert received_records[1]["metadata"]["calc_id"] == "c_zmq_2"
    assert np.allclose(received_records[1]["array"], [5.0, 6.0, 7.0])


# =============================================================================
# 5. SINGLE MASTER NODE GATEKEEPING
# =============================================================================

def test_is_master_node_detection() -> None:
    """Tests environment-aware master node detection."""
    for environment, expected in (
        ({"COCHEM_IS_MASTER": "1"}, True),
        ({"COCHEM_IS_MASTER": "0"}, False),
        ({"OMPI_COMM_WORLD_RANK": "0"}, True),
        ({"OMPI_COMM_WORLD_RANK": "3"}, False),
    ):
        _run_storage_process(
            """
            import sys
            from cochem_base.core.cochem_core_hdf5_manager import is_master_node
            assert is_master_node() is (sys.argv[1] == "True")
            """,
            expected,
            environment=environment,
        )

@pytest.mark.skipif(not os.environ.get("SLURM_PROCID"), reason="Requires physical SLURM node")
def test_is_master_node_detection_slurm() -> None:
    _run_storage_process(
        """
        import os
        from cochem_base.core.cochem_core_hdf5_manager import is_master_node
        assert is_master_node() is (os.environ["SLURM_PROCID"] == "0")
        """,
        preserve_slurm=True,
    )


def test_master_write_gatekeeper_rejection_and_forwarding(tmp_path: Path) -> None:
    """Verifies that non-master nodes are strictly forbidden from writing to HDF5 directly."""
    h5_path = tmp_path / "gatekeeper_test.h5"
    db_path = tmp_path / "gatekeeper_ipc.db"

    _run_storage_process(
        """
        import sys
        from cochem_base.core.cochem_core_hdf5_manager import BasinRecord, MasterWriteGatekeeper
        gatekeeper = MasterWriteGatekeeper(h5_path=sys.argv[1], ipc_db_path=sys.argv[2])
        assert gatekeeper.is_master is True
        basin = BasinRecord(molecule_name="serialization_fixture", energy=-40.5, symmetry_group="Td")
        gatekeeper.write_basin("basin_ch4", basin)
        """,
        h5_path, db_path,
        environment={"COCHEM_IS_MASTER": "1"},
    )
    assert h5_path.exists()
    _run_storage_process(
        """
        import sys
        import pytest
        from cochem_base.core.cochem_core_hdf5_manager import (
            BasinRecord, MasterWriteGatekeeper, NonMasterWriteRejectionError,
        )
        worker = MasterWriteGatekeeper(h5_path=sys.argv[1], ipc_db_path=sys.argv[2])
        assert worker.is_master is False
        basin = BasinRecord(molecule_name="serialization_fixture", energy=-40.5, symmetry_group="Td")
        with pytest.raises(NonMasterWriteRejectionError):
            worker.write_basin("basin_rejected", basin, allow_ipc_forward=False)
        assert worker.write_basin("basin_forwarded", basin, allow_ipc_forward=True) > 0
        """,
        h5_path, db_path,
        environment={"COCHEM_IS_MASTER": "0"},
    )
    _run_storage_process(
        """
        import sys
        from cochem_base.core.cochem_core_hdf5_manager import MasterDataAggregator
        aggregator = MasterDataAggregator(h5_path=sys.argv[1], ipc_db_path=sys.argv[2])
        assert aggregator.aggregate_pending(limit=10) == 1
        """,
        h5_path, db_path,
        environment={"COCHEM_IS_MASTER": "1"},
    )

    # Verify record in HDF5
    with h5py.File(h5_path, "r") as f:
        assert "basins/basin_rejected" not in f
        assert "basins/basin_forwarded" in f
        assert f["basins/basin_forwarded"].attrs["energy"] == -40.5


# =============================================================================
# 6. RIGOROUS HDF5 FILTERING (gzip + shuffle + fletcher32)
# =============================================================================

def test_hdf5_mandatory_filter_enforcement(tmp_path: Path) -> None:
    """Verifies that all created datasets strictly enforce gzip+shuffle+fletcher32 filters."""
    h5_path = tmp_path / "filtered_test.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_path)

    # Hand-entered 10x10 orbital-shaped matrix for filter serialization
    data_2d = np.array([
        [-0.9942,  0.2338,  0.0000, -0.1088,  0.0000, -0.1243,  0.0000,  0.0512, -0.0123,  0.0045],
        [-0.0267, -0.8444,  0.0000,  0.5381,  0.0000,  0.8197,  0.0000, -0.1245,  0.0345, -0.0089],
        [ 0.0000,  0.0000,  1.0000,  0.0000,  0.0000,  0.0000,  0.0000,  0.0000,  0.0000,  0.0000],
        [ 0.0000,  0.0000,  0.0000, -0.7583,  0.0000,  0.7719,  0.0000,  0.1567, -0.0456,  0.0123],
        [-0.0044, -0.1228,  0.0000,  0.0000,  0.7071,  0.0000,  0.6401, -0.0891,  0.0234, -0.0056],
        [-0.0051, -0.1556,  0.0000,  0.2827, -0.5000, -0.7642,  0.7103,  0.2012, -0.0678,  0.0178],
        [-0.0051, -0.1556,  0.0000,  0.2827,  0.5000, -0.7642, -0.7103, -0.2012,  0.0678, -0.0178],
        [ 0.0123, -0.0456,  0.0000,  0.1234,  0.0000,  0.1891,  0.0000, -0.9123,  0.3456, -0.0912],
        [-0.0034,  0.0123,  0.0000, -0.0456,  0.0000, -0.0678,  0.0000,  0.3456, -0.8912,  0.2845],
        [ 0.0012, -0.0045,  0.0000,  0.0123,  0.0000,  0.0234,  0.0000, -0.0912,  0.2845, -0.9512],
    ], dtype=np.float64)
    mgr.write_dataset_filtered(
        group_path="physics/orbitals",
        dataset_name="alpha_mo",
        data=data_2d,
        compression_opts=6,
    )

    with h5py.File(h5_path, "r") as f:
        dset = f["physics/orbitals/alpha_mo"]
        assert dset.compression == "gzip"
        assert dset.compression_opts == 6
        assert dset.shuffle is True
        assert dset.fletcher32 is True
        assert dset.chunks is not None
        assert np.array_equal(dset[()], data_2d)

        # Check filter verification utility
        filters_ok, details = verify_dataset_filters(dset)
        assert filters_ok is True
        assert details["compression"] == "gzip"
        assert details["shuffle"] is True
        assert details["fletcher32"] is True


def test_hdf5_filter_violation_rejection(tmp_path: Path) -> None:
    """Tests that attempts to bypass mandatory filters or pass banned scaleoffset raise HDF5FilterViolationError when strict."""
    h5_path = tmp_path / "filter_strict.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_path, strict_filters=True)

    # Hand-entered symmetric matrix for tensor conversion and serialization
    genuine_fock_matrix = np.array([
        [-20.2512,  -5.1234,   0.0000,  -1.2456,  -1.2456],
        [ -5.1234,  -1.3456,   0.0000,  -0.4567,  -0.4567],
        [  0.0000,   0.0000,  -0.7123,   0.0000,   0.0000],
        [ -1.2456,  -0.4567,   0.0000,  -0.6234,  -0.1234],
        [ -1.2456,  -0.4567,   0.0000,  -0.1234,  -0.6234],
    ], dtype=np.float64)

    # 1. Missing gzip compression -> Forbidden
    with pytest.raises(HDF5FilterViolationError, match="must use gzip compression"):
        mgr.write_dataset_filtered(
            group_path="bad_group",
            dataset_name="bad_dset_compression",
            data=genuine_fock_matrix,
            compression=None,
        )

    # 2. Missing fletcher32 checksum -> Forbidden
    with pytest.raises(HDF5FilterViolationError, match="must have fletcher32=True"):
        mgr.write_dataset_filtered(
            group_path="bad_group",
            dataset_name="bad_dset_fletcher32",
            data=genuine_fock_matrix,
            fletcher32=False,
        )

    # 3. Missing shuffle filter -> Forbidden
    with pytest.raises(HDF5FilterViolationError, match="must have shuffle=True"):
        mgr.write_dataset_filtered(
            group_path="bad_group",
            dataset_name="bad_dset_shuffle",
            data=genuine_fock_matrix,
            shuffle=False,
        )

    # 4. Method Matrix §8C: Lossy scaleoffset filter on energy/structural data -> Strictly Banned
    with pytest.raises(HDF5FilterViolationError, match="scaleoffset lossy compression filter is strictly banned"):
        mgr.write_dataset_filtered(
            group_path="bad_group",
            dataset_name="bad_dset_scaleoffset",
            data=genuine_fock_matrix,
            scaleoffset=4,
        )


# =============================================================================
# 7. FULL QCSCHEMA COMPLIANCE
# =============================================================================

def test_qcschema_models_and_serialization(tmp_path: Path) -> None:
    """Tests full QCSchema model validation, serialization, and round-trip from HDF5."""
    h5_path = tmp_path / "qcschema_landscape.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_path)

    # Construct QCSchema Molecule for H2O
    mol = QCSchemaMolecule(
        symbols=["O", "H", "H"],
        geometry=[0.0, 0.0, 0.0, 0.0, 1.4304, 1.1072, 0.0, -1.4304, 1.1072],
        molecular_charge=0.0,
        molecular_multiplicity=1,
    )

    # Hand-entered orbital-shaped serialization fixture (7x7)
    orbitals_h2o = np.array([
        [-0.9942,  0.2338,  0.0000, -0.1088,  0.0000, -0.1243,  0.0000],
        [-0.0267, -0.8444,  0.0000,  0.5381,  0.0000,  0.8197,  0.0000],
        [ 0.0000,  0.0000,  1.0000,  0.0000,  0.0000,  0.0000,  0.0000],
        [ 0.0000,  0.0000,  0.0000, -0.7583,  0.0000,  0.7719,  0.0000],
        [-0.0044, -0.1228,  0.0000,  0.0000,  0.7071,  0.0000,  0.6401],
        [-0.0051, -0.1556,  0.0000,  0.2827, -0.5000, -0.7642,  0.7103],
        [-0.0051, -0.1556,  0.0000,  0.2827,  0.5000, -0.7642, -0.7103],
    ], dtype=np.float64)

    occupations_h2o = np.array([2.0, 2.0, 2.0, 2.0, 2.0, 0.0, 0.0], dtype=np.float64)

    # Numerical density-shaped fixture formed as P_alpha = C_occ @ C_occ.T
    density_h2o_a = orbitals_h2o[:, :5] @ orbitals_h2o[:, :5].T

    # Construct QCSchema Wavefunction
    wf = QCSchemaWavefunction(
        basis="def2-TZVP",
        orbitals_a=orbitals_h2o,
        occupations_a=occupations_h2o,
        density_a=density_h2o_a,
    )

    # Construct AtomicResult
    res = QCSchemaAtomicResult(
        schema_name="qcschema_output",
        schema_version=1,
        molecule=mol,
        driver=QCSchemaDriver.ENERGY,
        model=QCSchemaModel(method="r2SCAN-3c", basis="def2-mTZVP"),
        return_result=-76.4321,
        properties=QCSchemaProperties(
            return_energy=-76.4321,
            scf_total_energy=-76.4321,
            nuclear_repulsion_energy=9.123,
        ),
        wavefunction=wf,
        success=True,
    )

    calc_id = "calc_h2o_r2scan"
    mgr.write_qcschema_result(calc_id=calc_id, result=res)

    # Read back from HDF5
    loaded_res = mgr.read_qcschema_result(calc_id=calc_id)
    assert loaded_res.schema_name == "qcschema_output"
    assert loaded_res.molecule.symbols == ["O", "H", "H"]
    assert len(loaded_res.molecule.geometry) == 9
    assert loaded_res.return_result == -76.4321
    assert loaded_res.properties.scf_total_energy == -76.4321
    assert loaded_res.wavefunction is not None
    assert loaded_res.wavefunction.basis == "def2-TZVP"
    assert np.allclose(loaded_res.wavefunction.orbitals_a, orbitals_h2o)
    assert np.allclose(loaded_res.wavefunction.occupations_a, occupations_h2o)
    assert np.allclose(loaded_res.wavefunction.density_a, density_h2o_a)

    # Verify that all wavefunction datasets in HDF5 have gzip+shuffle+fletcher32
    with h5py.File(h5_path, "r") as f:
        wf_grp = f[f"calculations/{calc_id}/wavefunction"]
        for dset_name in ["orbitals_a", "occupations_a", "density_a"]:
            dset = wf_grp[dset_name]
            ok, _ = verify_dataset_filters(dset)
            assert ok is True, f"Dataset {dset_name} did not pass filter verification"


def test_qcelemental_interoperability(tmp_path: Path) -> None:
    """Validate real QCElemental schema conversion using explicit serialization fixtures."""
    assert qcel is not None, "Install the required QCElemental schema package"
    h5_path = tmp_path / "qcel_interop.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_path)
    try:
        import qcelemental.models.v2 as v2
    except (ImportError, RuntimeError):
        from qcelemental.models import AtomicResult as V1AtomicResult
        from qcelemental.models import Molecule as V1Molecule
        mol = V1Molecule(
            symbols=["C", "O"],
            geometry=[0.0, 0.0, 0.0, 0.0, 0.0, 2.13],
            molecular_charge=0,
            molecular_multiplicity=1,
        )
        qcel_res = V1AtomicResult(
            molecule=mol,
            driver="energy",
            model={"method": "serialization_fixture", "basis": None},
            return_result=-113.123,
            properties={"return_energy": -113.123},
            provenance={"creator": "CoChem-serialization-fixture"},
            success=True,
        )
    else:
        mol = v2.Molecule(
            symbols=["C", "O"],
            geometry=[0.0, 0.0, 0.0, 0.0, 0.0, 2.13],
            molecular_charge=0,
            molecular_multiplicity=1,
        )
        spec = v2.AtomicSpecification(
            driver=v2.DriverEnum.energy,
            model=v2.Model(method="serialization_fixture", basis=None),
        )
        inp = v2.AtomicInput(molecule=mol, specification=spec)
        qcel_res = v2.AtomicResult(
            molecule=mol,
            input_data=inp,
            properties=v2.AtomicProperties(return_energy=-113.123),
            return_result=-113.123,
            provenance=v2.Provenance(creator="CoChem-serialization-fixture"),
            success=True,
        )
    calc_id = "qcel_serialization_fixture"
    mgr.write_qcschema_result(calc_id=calc_id, result=qcel_res)
    retrieved = mgr.read_qcschema_result(calc_id=calc_id)
    assert retrieved.molecule.symbols == ["C", "O"]
    assert retrieved.return_result == -113.123
    assert retrieved.success is True



# =============================================================================
# 8. LANDSCAPE DATABASE SERIALIZATION & BASIN RECORDS
# =============================================================================

def test_basin_and_landscape_lifecycle(tmp_path: Path) -> None:
    """Tests basin record serialization into landscape.h5 with metadata attributes."""
    h5_path = tmp_path / "landscape.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_path)

    coords = np.array([
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
    ], dtype=np.float64)

    record = BasinRecord(
        molecule_name="triatomic_complex",
        xyz_coordinates=coords,
        energy=-250.4567,
        symmetry_group="Cs",
        LAM_TRIGGER_REQUIRED=True,
    )

    mgr.write_basin_record("basin_triatomic", record)

    # Read back basin record
    loaded_basin = mgr.read_basin_record("basin_triatomic")
    assert loaded_basin.molecule_name == "triatomic_complex"
    assert loaded_basin.energy == -250.4567
    assert loaded_basin.symmetry_group == "Cs"
    assert loaded_basin.LAM_TRIGGER_REQUIRED is True
    assert np.allclose(loaded_basin.xyz_coordinates, coords)

    # List basins
    basins = mgr.list_basins()
    assert "basin_triatomic" in basins


def test_resolve_landscape_h5_path(tmp_path: Path) -> None:
    """New telemetry stores use the Chunk 17 filename."""
    _run_storage_process(
        """
        import sys
        from pathlib import Path
        from cochem_base.core.cochem_core_hdf5_manager import resolve_landscape_h5_path
        resolved = resolve_landscape_h5_path()
        assert resolved.name == "complexes.h5"
        assert "Databases" in resolved.parts
        assert resolved.is_relative_to(Path(sys.argv[1]))
        """,
        tmp_path,
        environment={"COCHEM_ARTIFACT_DIR": str(tmp_path)},
    )


# =============================================================================
# 9. ADVERSARIAL META-AUDITOR VALIDATIONS (ZERO-MOCK MANDATE)
# =============================================================================

def _compute_harmonic_fixture_geometry_and_hessian() -> Tuple[List[float], List[List[float]]]:
    """Construct a toy chain and finite-difference harmonic Hessian for storage tests.

    Coordinates use Bohr and the chosen toy potential uses Hartree. This is not
    an ab initio Hessian or a reference for a particular physical molecule.
    """
    n_atoms = 10
    bond_len = 2.9103  # Bohr (1.54 Angstrom)
    theta_eq = 1.9111  # Rad (109.5 degrees)

    # Toy zigzag-chain coordinates in Bohr
    coords: List[List[float]] = [[0.0, 0.0, 0.0]]
    for i in range(1, n_atoms):
        prev = coords[-1]
        sign = 1.0 if (i % 2 == 1) else -1.0
        dx = bond_len * np.cos(theta_eq / 2.0)
        dy = sign * bond_len * np.sin(theta_eq / 2.0)
        coords.append([float(prev[0] + dx), float(prev[1] + dy), 0.0])

    flat_geom: List[float] = [c for atom in coords for c in atom]
    x0 = np.array(flat_geom, dtype=np.float64)

    def potential(x: np.ndarray) -> float:
        r = x.reshape((n_atoms, 3))
        kb = 0.450  # Chosen toy-model stretch constant, Hartree / Bohr^2
        ka = 0.120  # Chosen toy-model bend constant, Hartree / rad^2
        v = 0.0
        for idx in range(n_atoms - 1):
            bond_dist = float(np.linalg.norm(r[idx + 1] - r[idx]))
            v += 0.5 * kb * ((bond_dist - bond_len) ** 2)
        for idx in range(n_atoms - 2):
            vec1 = r[idx] - r[idx + 1]
            vec2 = r[idx + 2] - r[idx + 1]
            dot_prod = float(np.dot(vec1, vec2))
            norm_prod = float(np.linalg.norm(vec1) * np.linalg.norm(vec2))
            cos_th = max(min(dot_prod / (norm_prod + 1e-14), 1.0), -1.0)
            ang = float(np.arccos(cos_th))
            v += 0.5 * ka * ((ang - theta_eq) ** 2)
        return v

    dim = n_atoms * 3
    hess = np.empty((dim, dim), dtype=np.float64)
    eps = 1e-4
    for i in range(dim):
        for j in range(i, dim):
            x_pp = x0.copy(); x_pp[i] += eps; x_pp[j] += eps
            x_pm = x0.copy(); x_pm[i] += eps; x_pm[j] -= eps
            x_mp = x0.copy(); x_mp[i] -= eps; x_mp[j] += eps
            x_mm = x0.copy(); x_mm[i] -= eps; x_mm[j] -= eps
            d2 = (potential(x_pp) - potential(x_pm) - potential(x_mp) + potential(x_mm)) / (4.0 * eps * eps)
            hess[i, j] = d2
            hess[j, i] = d2

    return flat_geom, hess.tolist()


def test_qcschema_optimization_result_serialization_and_roundtrip(tmp_path: Path) -> None:
    """Tests full QCSchema OptimizationResult serialization, trajectory steps, energies, and filter compliance."""
    h5_path = tmp_path / "opt_landscape.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_path)

    init_mol = QCSchemaMolecule(
        symbols=["C", "O"],
        geometry=[0.0, 0.0, 0.0, 0.0, 0.0, 2.50],
        molecular_charge=0.0,
        molecular_multiplicity=1,
    )
    final_mol = QCSchemaMolecule(
        symbols=["C", "O"],
        geometry=[0.0, 0.0, 0.0, 0.0, 0.0, 2.13],
        molecular_charge=0.0,
        molecular_multiplicity=1,
    )

    # Hand-entered density-shaped matrices for the optimization serialization fixture
    density_co_step_0 = np.array([
        [1.9842, 0.1245, 0.0000, 0.0312],
        [0.1245, 1.8756, 0.0000, -0.2145],
        [0.0000, 0.0000, 1.0000, 0.0000],
        [0.0312, -0.2145, 0.0000, 1.1402],
    ], dtype=np.float64)

    density_co_step_1 = np.array([
        [1.9895, 0.1582, 0.0000, 0.0421],
        [0.1582, 1.9124, 0.0000, -0.2678],
        [0.0000, 0.0000, 1.0000, 0.0000],
        [0.0421, -0.2678, 0.0000, 1.0981],
    ], dtype=np.float64)

    # Step 1
    step_0 = QCSchemaAtomicResult(
        schema_name="qcschema_output",
        schema_version=1,
        molecule=init_mol,
        driver=QCSchemaDriver.GRADIENT,
        model=QCSchemaModel(method="b3lyp", basis="6-31g*"),
        return_result=[[0.0, 0.0, 0.05], [0.0, 0.0, -0.05]],
        properties=QCSchemaProperties(return_energy=-113.050, scf_total_energy=-113.050),
        wavefunction=QCSchemaWavefunction(basis="6-31g*", density_a=density_co_step_0),
        success=True,
    )
    # Step 2
    step_1 = QCSchemaAtomicResult(
        schema_name="qcschema_output",
        schema_version=1,
        molecule=final_mol,
        driver=QCSchemaDriver.GRADIENT,
        model=QCSchemaModel(method="b3lyp", basis="6-31g*"),
        return_result=[[0.0, 0.0, 0.001], [0.0, 0.0, -0.001]],
        properties=QCSchemaProperties(return_energy=-113.123, scf_total_energy=-113.123),
        wavefunction=QCSchemaWavefunction(basis="6-31g*", density_a=density_co_step_1),
        success=True,
    )

    opt_result = QCSchemaOptimizationResult(
        schema_name="qcschema_optimization_output",
        schema_version=1,
        initial_molecule=init_mol,
        final_molecule=final_mol,
        trajectory=[step_0, step_1],
        energies=[-113.050, -113.123],
        provenance={"creator": "CoChem-Opt-Test", "version": "4.0.0"},
        success=True,
    )

    opt_id = "opt_co_relax_01"
    mgr.write_qcschema_optimization_result(opt_id=opt_id, result=opt_result)

    # List trajectories
    trajs = mgr.list_trajectories()
    assert opt_id in trajs

    # Read back and assert full round-trip fidelity
    loaded_opt = mgr.read_qcschema_optimization_result(opt_id=opt_id)
    assert loaded_opt.schema_name == "qcschema_optimization_output"
    assert loaded_opt.success is True
    assert loaded_opt.provenance.get("creator") == "CoChem-Opt-Test"
    assert len(loaded_opt.trajectory) == 2
    assert np.allclose(loaded_opt.energies, [-113.050, -113.123])
    assert loaded_opt.initial_molecule.symbols == ["C", "O"]
    assert np.allclose(loaded_opt.initial_molecule.geometry, [0.0, 0.0, 0.0, 0.0, 0.0, 2.50])
    assert loaded_opt.final_molecule.symbols == ["C", "O"]
    assert np.allclose(loaded_opt.final_molecule.geometry, [0.0, 0.0, 0.0, 0.0, 0.0, 2.13])

    # Check step 0 & step 1 wavefunction density tensors
    assert loaded_opt.trajectory[0].driver == QCSchemaDriver.GRADIENT
    assert loaded_opt.trajectory[0].properties.return_energy == -113.050
    assert loaded_opt.trajectory[0].wavefunction is not None
    assert np.allclose(loaded_opt.trajectory[0].wavefunction.density_a, density_co_step_0)
    assert np.allclose(loaded_opt.trajectory[1].wavefunction.density_a, density_co_step_1)

    # Verify that all datasets in the optimization hierarchy enforce gzip+shuffle+fletcher32
    integrity = mgr.verify_file_integrity()
    assert integrity["total_datasets"] > 0
    assert len(integrity["filter_violations"]) == 0
    assert len(integrity["corrupted_datasets"]) == 0
    assert integrity["valid_datasets"] == integrity["total_datasets"]


def test_gradient_and_hessian_filtered_dataset_serialization(tmp_path: Path) -> None:
    """Tests that large gradients and Hessians are stored as chunked filtered datasets with Fletcher32 checksums."""
    h5_path = tmp_path / "hessian_landscape.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_path)

    # 10-site toy chain -> 30x30 finite-difference Hessian serialization fixture
    n_atoms = 10
    symbols = ["C"] * n_atoms
    geom, hessian_matrix = _compute_harmonic_fixture_geometry_and_hessian()

    res = QCSchemaAtomicResult(
        schema_name="qcschema_output",
        schema_version=1,
        molecule=QCSchemaMolecule(symbols=symbols, geometry=geom),
        driver=QCSchemaDriver.HESSIAN,
        model=QCSchemaModel(method="pbe0", basis="def2-SVP"),
        return_result=hessian_matrix,
        properties=QCSchemaProperties(return_energy=-380.123),
        success=True,
    )

    calc_id = "calc_c10_hessian"
    mgr.write_qcschema_result(calc_id=calc_id, result=res)

    # Verify physical HDF5 dataset filters on the return_result dataset
    with h5py.File(h5_path, "r") as f:
        dset = f[f"calculations/{calc_id}/return_result"]
        ok, details = verify_dataset_filters(dset)
        assert ok is True, f"Return result dataset failed filter verification: {details}"
        assert dset.shape == (30, 30)

    # Read back and assert exact numerical identity
    loaded_res = mgr.read_qcschema_result(calc_id=calc_id)
    assert loaded_res.driver == QCSchemaDriver.HESSIAN
    assert np.allclose(loaded_res.return_result, hessian_matrix)


def test_method_matrix_scaleoffset_strict_rejection_and_verification(tmp_path: Path) -> None:
    """Verifies Method Matrix §8C strict ban on lossy scaleoffset filter.
    
    Validates:
    1. write_dataset_filtered directly raises HDF5FilterViolationError when scaleoffset is specified.
    2. CoChemHDF5Manager.write_dataset_filtered raises HDF5FilterViolationError.
    3. verify_dataset_filters detects and invalidates any dataset created with scaleoffset filter.
    4. verify_file_integrity flags datasets with scaleoffset as filter violations.
    """
    h5_path = tmp_path / "scaleoffset_audit.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_path, strict_filters=True)

    energy_data = np.array([-76.4321987654321, -76.4051234567890], dtype=np.float64)

    # 1. CoChemHDF5Manager write rejection
    with pytest.raises(HDF5FilterViolationError, match="scaleoffset lossy compression filter is strictly banned"):
        mgr.write_dataset_filtered("energies", "pes_surface", energy_data, scaleoffset=4)

    # 2. Raw write_dataset_filtered direct rejection
    with h5py.File(h5_path, "a") as f:
        with pytest.raises(HDF5FilterViolationError, match="scaleoffset lossy compression filter is strictly banned"):
            write_dataset_filtered(f, "raw_banned_scaleoffset", energy_data, scaleoffset=2)

    # 3. Simulate an external file containing a scaleoffset dataset and verify audit detection
    with h5py.File(h5_path, "a") as f:
        # Directly bypass through low-level h5py create_dataset to simulate external malformed HDF5
        f.create_dataset("external_lossy_dset", data=energy_data, scaleoffset=2, chunks=True)
        scaleoffset_dset = f["external_lossy_dset"]
        is_valid, details = verify_dataset_filters(scaleoffset_dset)
        assert is_valid is False
        assert details["scaleoffset"] == 2

    # 4. verify_file_integrity reports the scaleoffset violation
    integrity = mgr.verify_file_integrity()
    assert len(integrity["filter_violations"]) > 0
    violation_paths = [v["path"] for v in integrity["filter_violations"]]
    assert "external_lossy_dset" in violation_paths


def test_scalar_dataset_normalization_and_filtering(tmp_path: Path) -> None:
    """Tests that 0D scalars and 1D arrays are normalized and successfully filtered with gzip+shuffle+fletcher32."""
    h5_path = tmp_path / "scalar_filtered.h5"
    mgr = CoChemHDF5Manager(h5_path=h5_path)

    mgr.write_dataset_filtered("scalars", "pi_val", np.array(3.141592653589793))
    mgr.write_dataset_filtered("scalars", "single_str", "benzene_ring")

    with h5py.File(h5_path, "r") as f:
        pi_dset = f["scalars/pi_val"]
        ok_pi, _ = verify_dataset_filters(pi_dset)
        assert ok_pi is True
        assert np.isclose(pi_dset[0], 3.141592653589793)

        str_dset = f["scalars/single_str"]
        ok_str, _ = verify_dataset_filters(str_dset)
        assert ok_str is True


def test_swmr_eradication_ast_attribute_detection() -> None:
    """Tests that verify_no_swmr_usage detects and rejects swmr_mode assignments in source code."""
    bad_code_1 = "import h5py\nf = h5py.File('test.h5', swmr=True)"
    with pytest.raises(HDF5ManagerError, match="SWMR Violation"):
        verify_no_swmr_usage(bad_code_1)

    bad_code_2 = "import h5py\nf = h5py.File('test.h5', libver='latest')"
    with pytest.raises(HDF5ManagerError, match="SWMR Violation"):
        verify_no_swmr_usage(bad_code_2)

    bad_code_3 = "f.swmr_mode = True"
    with pytest.raises(HDF5ManagerError, match="SWMR Violation"):
        verify_no_swmr_usage(bad_code_3)


def test_master_aggregator_optimization_stream(tmp_path: Path) -> None:
    """Round-trip a declared serialization fixture through actual worker/master processes."""
    h5_path = tmp_path / "stream_landscape.h5"
    db_path = tmp_path / "stream_ipc.db"
    _run_storage_process(
        """
        import sys
        from cochem_base.core.cochem_core_hdf5_manager import SQLiteWALQueue, is_master_node
        assert is_master_node() is False
        queue = SQLiteWALQueue(db_path=sys.argv[1])
        init_mol = {"symbols": ["H", "F"], "geometry": [0.0, 0.0, 0.0, 0.0, 0.0, 1.2]}
        final_mol = {"symbols": ["H", "F"], "geometry": [0.0, 0.0, 0.0, 0.0, 0.0, 0.92]}
        fixture_provenance = {"creator": "serialization_fixture", "physical_reference": False}
        step = {
            "schema_name": "qcschema_output",
            "schema_version": 1,
            "molecule": init_mol,
            "driver": "energy",
            "model": {"method": "serialization_fixture", "basis": "not_applicable"},
            "return_result": -100.0,
            "properties": {"return_energy": -100.0},
            "provenance": fixture_provenance,
            "success": True,
        }
        opt_payload = {
            "opt_id": "opt_fixture_stream_01",
            "data": {
                "schema_name": "qcschema_optimization_output",
                "schema_version": 1,
                "initial_molecule": init_mol,
                "final_molecule": final_mol,
                "trajectory": [step],
                "energies": [-100.0],
                "provenance": fixture_provenance,
                "success": True,
            },
        }
        queue.push(topic="optimization_stream", payload=opt_payload, sender="worker_node_42")
        assert queue.count_pending() == 1
        """,
        db_path,
        environment={"COCHEM_IS_MASTER": "0"},
    )
    _run_storage_process(
        """
        import sys
        from cochem_base.core.cochem_core_hdf5_manager import (
            MasterDataAggregator, SQLiteWALQueue, is_master_node,
        )
        assert is_master_node() is True
        aggregator = MasterDataAggregator(h5_path=sys.argv[1], ipc_db_path=sys.argv[2])
        assert aggregator.aggregate_pending(limit=10) == 1
        assert SQLiteWALQueue(db_path=sys.argv[2]).count_pending() == 0
        """,
        h5_path, db_path,
        environment={"COCHEM_IS_MASTER": "1"},
    )
    mgr = CoChemHDF5Manager(h5_path=h5_path, ipc_db_path=db_path)
    assert "opt_fixture_stream_01" in mgr.list_trajectories()
    loaded = mgr.read_qcschema_optimization_result("opt_fixture_stream_01")
    assert loaded.initial_molecule.symbols == ["H", "F"]
    assert loaded.energies == [-100.0]
    assert loaded.provenance["physical_reference"] is False
