"""Unit tests for Pure-Wheel Fast IPC Serialization & HDF5 PESStore.
Strictly adheres to Zero-Mock mandate and authentic binary serialization.
"""

import pathlib
import uuid

import h5py
import numpy as np
import pytest

from cochem.core.context import AirGapViolationError, ExecutionContext, scoped_context
from cochem.core.ingestors.protocols import MolecularStructureData, QCResultsSchema
from cochem.core.ipc.serializer import (
    HMACSocketClient,
    HMACSocketServer,
    PESStore,
    SharedMemoryBuffer,
    pack_payload,
    unpack_payload,
)


def test_msgpack_numpy_roundtrip() -> None:
    """Verify Msgpack custom extension serialization preserves NumPy array dtype, shape, and data."""
    # Authentic 3D coordinate array
    original_arr = np.array(
        [
            [0.0, 0.0, 0.1173],
            [0.0, 0.7572, -0.4692],
            [0.0, -0.7572, -0.4692],
        ],
        dtype=np.float64,
    )

    packed = pack_payload({"coordinates": original_arr, "label": "water_coordinates"})
    unpacked = unpack_payload(packed)

    recovered_arr = unpacked["coordinates"]
    assert isinstance(recovered_arr, np.ndarray)
    assert recovered_arr.dtype == original_arr.dtype
    assert recovered_arr.shape == original_arr.shape
    assert np.allclose(recovered_arr, original_arr)
    assert unpacked["label"] == "water_coordinates"


def test_msgpack_pydantic_schema_roundtrip() -> None:
    """Verify pack_payload correctly serializes MolecularStructureData and QCResultsSchema."""
    mol = MolecularStructureData(
        symbols=["H", "H"],
        coordinates=[(0.0, 0.0, 0.0), (0.0, 0.0, 0.74)],
        charge=0,
        multiplicity=1,
    )

    qc = QCResultsSchema(
        total_energy=-1.137,
        gradient=[0.0, 0.0, -0.001, 0.0, 0.0, 0.001],
        frequencies=[4401.2],
        dipole_moment=(0.0, 0.0, 0.0),
        rotational_constants=(0.0, 1780.0, 1780.0),
    )

    packed = pack_payload({"mol": mol, "qc": qc})
    unpacked = unpack_payload(packed)

    recovered_mol = MolecularStructureData.model_validate(unpacked["mol"])
    recovered_qc = QCResultsSchema.model_validate(unpacked["qc"])

    assert recovered_mol.symbols == ["H", "H"]
    assert len(recovered_mol.masses) == 2
    assert recovered_qc.total_energy == -1.137
    assert len(recovered_qc.gradient) == 6


def test_shared_memory_buffer_roundtrip() -> None:
    """Verify shared memory descriptor allocation and zero-copy recreation."""
    # Allocate authentic 1 MB array
    arr = np.full(shape=(128, 1024), fill_value=3.1415926535, dtype=np.float64)

    shm_buffer = SharedMemoryBuffer.from_array(arr)
    descriptor = shm_buffer.descriptor

    # Consumer process reconstructs from descriptor
    recovered = SharedMemoryBuffer.read_from_descriptor(descriptor)
    try:
        assert np.allclose(recovered, arr)
        assert recovered.shape == (128, 1024)
        assert recovered.dtype == np.float64
    finally:
        shm_buffer.close()
        shm_buffer.unlink()


def test_hmac_socket_transport_exchange() -> None:
    """Verify loopback TCP socket with ephemeral HMAC-SHA256 handshake exchange."""
    shared_key = b"authentic_cochem_hmac_secret_2026"
    server = HMACSocketServer(host="127.0.0.1", port=0, secret_key=shared_key)
    server.start()

    try:
        assigned_port = server.port
        client = HMACSocketClient(host="127.0.0.1", port=assigned_port, secret_key=shared_key)

        test_data = {"energy": -76.432, "step": 12}
        client.send_payload(test_data)

        received = server.get_received_payload(timeout_sec=3.0)
        assert received is not None
        assert received["energy"] == -76.432
        assert received["step"] == 12
    finally:
        server.stop()


def test_pes_store_persistence_and_swmr(tmp_path: pathlib.Path) -> None:
    """Verify HDF5 PESStore QCSchema compliance, Gzip compression, and SWMR read-back."""
    store_file = tmp_path / "pes_landscape.h5"
    store = PESStore(store_file)

    energy_surface = np.array(
        [
            [-76.432, -76.430, -76.425],
            [-76.428, -76.424, -76.419],
            [-76.420, -76.415, -76.408],
        ],
        dtype=np.float64,
    )

    molecule_dict = {
        "symbols": ["O", "H", "H"],
        "coordinates": [[0.0, 0.0, 0.117], [0.0, 0.757, -0.469], [0.0, -0.757, -0.469]],
    }

    # Atomic write to HDF5
    store.write_entry(
        entry_id="point_001",
        molecule=molecule_dict,
        driver="energy",
        model={"method": "B3LYP-D4", "basis": "def2-TZVP"},
        return_result=energy_surface,
    )

    assert store_file.exists()

    # Read back and inspect HDF5 attributes and datasets
    with h5py.File(store_file, "r", libver="latest", swmr=True) as h5f:
        grp = h5f["point_001"]
        assert grp.attrs["schema_name"] == "qcschema_output"
        assert grp.attrs["driver"] == "energy"
        dset = grp["return_result"]
        assert dset.compression == "gzip"
        loaded_res = dset[:]
        assert np.allclose(loaded_res, energy_surface)

    # Load via PESStore reader method
    entry = store.read_entry("point_001")
    assert entry["schema_name"] == "qcschema_output"
    assert np.allclose(entry["return_result"], energy_surface)


def test_pes_store_blocks_airgap_violation(tmp_path: pathlib.Path) -> None:
    """Verify PESStore rejects attempts to persist into read-only $COCH_SRC tier."""
    src_dir = tmp_path / "cochem_src"
    data_dir = tmp_path / "cochem_data"
    artifacts_dir = tmp_path / "cochem_artifacts"
    scratch_dir = artifacts_dir / "scratch"

    src_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    scratch_dir.mkdir(parents=True, exist_ok=True)

    ctx = ExecutionContext(
        execution_id=str(uuid.uuid4()),
        session_name="test_pes_airgap",
        src_dir=src_dir,
        data_dir=data_dir,
        artifacts_dir=artifacts_dir,
        scratch_dir=scratch_dir,
        env_tier="Tier 1A",
    )

    with scoped_context(ctx):
        illegal_file = src_dir / "illegal_pes.h5"
        with pytest.raises(AirGapViolationError):
            PESStore(illegal_file)
