"""Zero-Mock Physics Invariants, Memory, and IPC Test Suite (Part 4).
Validates Suggestions #34, #35, #36, #38, and #39.
Adheres strictly to Method Matrix v4 and Zero-Mock Anti-Spoofing Protocol v3.
"""

from __future__ import annotations

import gc
import hashlib
import hmac
import multiprocessing.shared_memory as sm
import pathlib
import secrets
import socket
import struct
import threading
from typing import Any, Dict

import numpy as np
import pytest

from cochem.core.ingestors.protocols import (
    HessianSymmetryError,
    MendeleevInvariantError,
    MolecularStructureData,
    QCResultsSchema,
    QCValidationError,
    SpinContaminationError,
)
from cochem.core.ipc.serializer import (
    HMACSocketServer,
    OversizedPayloadError,
    PESStore,
    SharedMemoryBuffer,
    TruncatedPayloadError,
)


def test_hdf5_pes_store_swmr_concurrent_writes(tmp_path: pathlib.Path) -> None:
    """Validate multi-threaded concurrent appends to PESStore in SWMR mode without data loss or monolithic copies."""
    store_file = tmp_path / "pes_surface.h5"
    store = PESStore(store_file)

    num_threads = 4
    entries_per_thread = 20
    total_entries = num_threads * entries_per_thread

    errors: list[Exception] = []

    def worker_write(thread_id: int) -> None:
        for idx in range(entries_per_thread):
            entry_id = f"calc_t{thread_id}_idx{idx}"
            # Physical 3D coordinates for triatomic molecule
            coords = np.array(
                [
                    [0.0, 0.0, 0.0],
                    [0.0, 0.757, 0.586],
                    [0.0, -0.757, 0.586],
                ],
                dtype=np.float64,
            ) + (thread_id * 0.1 + idx * 0.01)

            molecule = {
                "symbols": ["O", "H", "H"],
                "geometry": coords.tolist(),
                "molecular_charge": 0,
                "molecular_multiplicity": 1,
            }
            model = {"method": "B3LYP", "basis": "def2-TZVP"}

            try:
                store.write_entry(
                    entry_id=entry_id,
                    molecule=molecule,
                    driver="energy",
                    model=model,
                    return_result=coords,
                )
            except Exception as e:
                errors.append(e)

    threads = [
        threading.Thread(target=worker_write, args=(t_id,), daemon=True)
        for t_id in range(num_threads)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15.0)

    assert not errors, f"Concurrent PES writes encountered errors: {errors}"
    assert store_file.exists()

    # Read back all 80 entries in SWMR mode and verify numerical fidelity
    for t_id in range(num_threads):
        for idx in range(entries_per_thread):
            entry_id = f"calc_t{t_id}_idx{idx}"
            read_data = store.read_entry(entry_id)
            assert read_data["entry_id"] == entry_id
            assert read_data["driver"] == "energy"
            assert read_data["model"]["method"] == "B3LYP"

            expected_coords = np.array(
                [
                    [0.0, 0.0, 0.0],
                    [0.0, 0.757, 0.586],
                    [0.0, -0.757, 0.586],
                ],
                dtype=np.float64,
            ) + (t_id * 0.1 + idx * 0.01)

            np.testing.assert_allclose(read_data["return_result"], expected_coords, rtol=1e-5)


def test_ipc_socket_payload_framing_and_truncation() -> None:
    """Validate loopback HMAC challenge authentication, truncation diagnostics, and 256 MB payload ceiling."""
    secret_key = secrets.token_bytes(32)
    server = HMACSocketServer(host="127.0.0.1", port=0, secret_key=secret_key)
    server.start()

    try:
        # Scenario 1: Truncated Payload Transmission (< declared header length)
        sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock1.connect((server.host, server.port))

        # Perform valid HMAC handshake
        challenge1 = sock1.recv(32)
        assert len(challenge1) == 32
        resp1 = hmac.new(secret_key, challenge1, hashlib.sha256).digest()
        sock1.sendall(resp1)
        status1 = sock1.recv(6)
        assert status1 == b"ACCEPT"

        # Transmit 4-byte header specifying 1000 bytes, but only send 200 bytes before closing
        sock1.sendall(struct.pack("!I", 1000))
        sock1.sendall(b"A" * 200)
        sock1.close()

        with pytest.raises(TruncatedPayloadError, match="Stream truncated"):
            server.get_received_payload(timeout_sec=3.0)

        # Scenario 2: Oversized Payload Transmission (> 256 MB ceiling)
        sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock2.connect((server.host, server.port))

        challenge2 = sock2.recv(32)
        assert len(challenge2) == 32
        resp2 = hmac.new(secret_key, challenge2, hashlib.sha256).digest()
        sock2.sendall(resp2)
        status2 = sock2.recv(6)
        assert status2 == b"ACCEPT"

        # Transmit header specifying 500 MB (exceeds 256 MB limit)
        oversized_len = 500 * 1024 * 1024
        sock2.sendall(struct.pack("!I", oversized_len))
        sock2.close()

        with pytest.raises(OversizedPayloadError, match="exceeds 256 MB limit"):
            server.get_received_payload(timeout_sec=3.0)

    finally:
        server.stop()


def test_shared_memory_raii_and_weakref_cleanup() -> None:
    """Validate RAII context management and weakref garbage collection for OS shared memory segments."""
    arr = np.linspace(0.0, 100.0, 5000, dtype=np.float64)

    # 1. RAII Context Manager lifecycle
    shm_name: str
    with SharedMemoryBuffer.from_array(arr) as shm_buf:
        shm_name = shm_buf.shm.name
        read_arr = SharedMemoryBuffer.read_from_descriptor(shm_buf.descriptor)
        np.testing.assert_array_equal(arr, read_arr)

    # After exiting context, segment is unlinked
    with pytest.raises((FileNotFoundError, OSError)):
        sm.SharedMemory(name=shm_name)

    # 2. Garbage collection & weakref finalizer lifecycle
    shm_buf2 = SharedMemoryBuffer.from_array(arr)
    shm_name2 = shm_buf2.shm.name

    # Validate segment exists while reference is held
    active_shm = sm.SharedMemory(name=shm_name2)
    active_shm.close()

    del shm_buf2
    gc.collect()

    # After garbage collection, weakref finalizer has unlinked the OS segment
    with pytest.raises((FileNotFoundError, OSError)):
        sm.SharedMemory(name=shm_name2)


def test_mendeleev_mass_invariants_and_zero_mass_rejection() -> None:
    """Validate dynamic mass resolution via Mendeleev and strict rejection of zero masses."""
    # 1. Standard molecules (H2O, CH4)
    h2o_dict = {
        "symbols": ["O", "H", "H"],
        "coordinates": [
            [0.0, 0.0, 0.0],
            [0.0, 0.757, 0.586],
            [0.0, -0.757, 0.586],
        ],
        "charge": 0,
        "multiplicity": 1,
    }
    h2o_mol = MolecularStructureData(**h2o_dict)
    assert len(h2o_mol.masses) == 3
    assert pytest.approx(h2o_mol.masses[0], rel=1e-3) == 15.999
    assert pytest.approx(h2o_mol.masses[1], rel=1e-3) == 1.008
    assert pytest.approx(h2o_mol.masses[2], rel=1e-3) == 1.008

    ch4_dict = {
        "symbols": ["C", "H", "H", "H", "H"],
        "coordinates": [
            [0.0, 0.0, 0.0],
            [0.629, 0.629, 0.629],
            [-0.629, -0.629, 0.629],
            [-0.629, 0.629, -0.629],
            [0.629, -0.629, -0.629],
        ],
        "charge": 0,
        "multiplicity": 1,
    }
    ch4_mol = MolecularStructureData(**ch4_dict)
    assert len(ch4_mol.masses) == 5
    assert pytest.approx(ch4_mol.masses[0], rel=1e-3) == 12.011

    # 2. Exotic transuranic element without standard CIAAW weights (e.g. element 119)
    # Must raise MendeleevInvariantError and never return 0.0
    uue_dict = {
        "symbols": ["Uue"],
        "coordinates": [[0.0, 0.0, 0.0]],
        "charge": 0,
        "multiplicity": 1,
    }
    with pytest.raises(MendeleevInvariantError):
        MolecularStructureData.validate_and_resolve_molecular_data(uue_dict)

    # 3. Transuranic element with explicit isotope specified (e.g. Cf-252)
    cf_dict = {
        "symbols": ["Cf"],
        "coordinates": [[0.0, 0.0, 0.0]],
        "charge": 0,
        "multiplicity": 1,
        "isotopes": [252],
    }
    cf_mol = MolecularStructureData(**cf_dict)
    assert len(cf_mol.masses) == 1
    assert cf_mol.masses[0] > 0.0
    assert pytest.approx(cf_mol.masses[0], rel=1e-2) == 252.08


def test_spin_contamination_and_hessian_domain_exceptions() -> None:
    """Validate dedicated physical exception hierarchy for spin contamination and asymmetric Hessians."""
    # 1. Spin Contamination Error: <S^2>_calc = 1.25 for ideal singlet (S^2_ref = 0.0)
    contaminated_results: Dict[str, Any] = {
        "total_energy": -76.4215,
        "s2_expectation": 1.25,
        "s2_ideal": 0.0,
    }

    with pytest.raises(SpinContaminationError) as exc_spin:
        QCResultsSchema.validate_qc_results(contaminated_results)

    spin_err = exc_spin.value
    assert isinstance(spin_err, QCValidationError)
    assert spin_err.s2_calc == 1.25
    assert spin_err.s2_ref == 0.0
    assert spin_err.deviation_percent > 10.0

    # 2. Hessian Symmetry Error: |H_01 - H_10| = 0.05 > 1e-5
    asym_hessian = [
        [0.50, 0.05, 0.00],
        [0.00, 0.50, 0.00],
        [0.00, 0.00, 0.50],
    ]
    asym_results: Dict[str, Any] = {
        "total_energy": -76.4215,
        "hessian": asym_hessian,
    }

    with pytest.raises(HessianSymmetryError) as exc_hess:
        QCResultsSchema.validate_qc_results(asym_results)

    hess_err = exc_hess.value
    assert isinstance(hess_err, QCValidationError)
    assert hess_err.max_asymmetry == pytest.approx(0.05, abs=1e-6)
    assert hess_err.indices == (0, 1)
