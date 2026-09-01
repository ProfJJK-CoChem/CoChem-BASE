"""
Physical Unit and Integration Test Suite for CoChem Core Engine.

Validates:
1. AUD-01: HDF5 Ontology Enforcer container verification (tensor shapes, dtypes, exact coordinates,
   and group attributes: molecule_name, energy, symmetry_group, LAM_TRIGGER_REQUIRED).
2. AUD-02: ZeroMQ PUB/SUB Daemon lifecycle, real physical IPC transport delivery via sockets,
   Pydantic schema validation boundaries, and unstarted runtime error failure paths.
3. AUD-03: Dual schema validation and physical commit in write_dataset_with_attributes
   (BasinRecord and CoChemConfig compliance and schema rejection on invalid payloads).
4. AUD-04: Method Matrix §8C HDF5 Store Compliance (PESStore chunking, gzip+shuffle+fletcher32,
   lossy scaleoffset rejection, resizability, QCSchema provenance, grid registration, todo pattern,
   Delta-learning pairs, and DVR grid reshaping).

Zero-Mock Policy: All tests execute against physical HDF5 containers and genuine ZeroMQ sockets.
"""

from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from typing import Any, Dict

import h5py
import numpy as np
import pytest
import zmq
import zmq.asyncio
from pydantic import ValidationError

from core_engine.cochem_base_daemon import BaseDaemon, TelemetryPayload, ZeroMQDaemon
from core_engine.cochem_base_hdf5 import BasinRecord, CoChemHDF5Manager, HDF5OntologyEnforcer
from cochem_base.core.models import CoChemConfig
from core_engine.cochem_core_pes_store import PESStore


def get_free_port() -> int:
    """Dynamically allocate an unused ephemeral TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


# =============================================================================
# AUD-02: ZeroMQ Daemon Lifecycle, Real Physical IPC, and Schema Boundaries
# =============================================================================

def test_zeromq_daemon_lifecycle_and_unstarted_failure() -> None:
    """Test BaseDaemon lifecycle and verify failure paths when not started."""
    async def _test() -> None:
        pub_port = get_free_port()
        sub_port = get_free_port()
        daemon = BaseDaemon(pub_port=pub_port, sub_port=sub_port)

        # Failure paths before start()
        with pytest.raises(RuntimeError, match="ZeroMQDaemon is not running"):
            await daemon.publish("system/status", {"node_id": "test_node"})

        with pytest.raises(RuntimeError, match="ZeroMQDaemon is not running"):
            await daemon.recv_message()

        with pytest.raises(RuntimeError, match="ZeroMQDaemon is not running"):
            await daemon.listen_for_events()

        # Start lifecycle
        await daemon.start()
        assert daemon._running is True
        assert daemon.pub_socket is not None
        assert daemon.sub_socket is not None

        # Stop lifecycle
        await daemon.stop()
        assert daemon._running is False
        assert daemon.pub_socket is None
        assert daemon.sub_socket is None

    asyncio.run(_test())


def test_zeromq_daemon_physical_ipc_transport() -> None:
    """Test physical IPC transport delivery across genuine ZeroMQ PUB and SUB sockets."""
    async def _test() -> None:
        pub_port = get_free_port()
        sub_port = get_free_port()

        ext_ctx = zmq.asyncio.Context()
        try:
            # 1. External PUB binds to sub_port before daemon SUB connects
            ext_pub = ext_ctx.socket(zmq.PUB)
            ext_pub.bind(f"tcp://127.0.0.1:{sub_port}")

            # 2. Daemon starts (binds pub_port, connects sub_socket to sub_port)
            daemon = ZeroMQDaemon(pub_port=pub_port, sub_port=sub_port)
            await daemon.start()

            # 3. External SUB connects to daemon PUB socket
            ext_sub = ext_ctx.socket(zmq.SUB)
            ext_sub.connect(f"tcp://127.0.0.1:{pub_port}")
            ext_sub.setsockopt_string(zmq.SUBSCRIBE, "")

            # Allow ZMQ slow-joiner subscription to synchronize
            await asyncio.sleep(0.3)

            # Test A: daemon.publish -> ext_sub
            payload = {
                "node_id": "cochem_worker_1",
                "state": "IDLE",
                "uptime_seconds": 120,
            }
            await daemon.publish("system/status", payload)

            raw_topic, raw_payload = await asyncio.wait_for(ext_sub.recv_multipart(), timeout=3.0)
            assert raw_topic.decode("utf-8") == "system/status"
            received_dict = json.loads(raw_payload.decode("utf-8"))
            assert received_dict["node_id"] == "cochem_worker_1"
            assert received_dict["state"] == "IDLE"
            assert received_dict["uptime_seconds"] == 120

            # Test B: daemon.broadcast_state -> ext_sub
            broadcast_payload = {"step": 4, "converged": True, "energy": -76.4}
            await daemon.broadcast_state("state/broadcast", broadcast_payload)

            raw_topic, raw_payload = await asyncio.wait_for(ext_sub.recv_multipart(), timeout=3.0)
            assert raw_topic.decode("utf-8") == "state/broadcast"
            received_dict = json.loads(raw_payload.decode("utf-8"))
            assert received_dict["step"] == 4
            assert received_dict["converged"] is True

            # Test C: ext_pub -> daemon.recv_message()
            incoming_payload = {"job_id": "job_99", "task": "geometry_opt", "status": "RUNNING"}
            await ext_pub.send_multipart([
                b"telemetry/jobs",
                json.dumps(incoming_payload).encode("utf-8"),
            ])

            topic, data = await asyncio.wait_for(daemon.recv_message(), timeout=3.0)
            assert topic == "telemetry/jobs"
            assert data["job_id"] == "job_99"
            assert data["task"] == "geometry_opt"
            assert data["status"] == "RUNNING"

            # Test D: ext_pub -> daemon.listen_for_events()
            event_payload = {"event_type": "ENERGY_DROP", "delta_e": -0.005}
            await ext_pub.send_multipart([
                b"events/energy",
                json.dumps(event_payload).encode("utf-8"),
            ])

            topic, data = await asyncio.wait_for(daemon.listen_for_events(), timeout=3.0)
            assert topic == "events/energy"
            assert data["event_type"] == "ENERGY_DROP"
            assert data["delta_e"] == pytest.approx(-0.005)

            # Test E: Boundary validation on malformed JSON payload
            await ext_pub.send_multipart([b"events/corrupt", b"{malformed_non_json"])
            with pytest.raises(ValidationError):
                await asyncio.wait_for(daemon.recv_message(), timeout=3.0)

            ext_sub.close()
            ext_pub.close()
        finally:
            ext_ctx.term()
            await daemon.stop()

    asyncio.run(_test())


def test_zeromq_daemon_independent_servers() -> None:
    """Test start_pub_server and start_sub_listener standalone invocation."""
    async def _test() -> None:
        pub_p = get_free_port()
        sub_p = get_free_port()
        daemon = BaseDaemon()

        await daemon.start_pub_server(port=pub_p)
        assert daemon._running is True
        assert daemon.pub_socket is not None

        await daemon.start_sub_listener(port=sub_p)
        assert daemon.sub_socket is not None

        await daemon.stop()
        assert daemon._running is False

    asyncio.run(_test())


# =============================================================================
# AUD-01: HDF5 Ontology Enforcer Physical Container & Tensor Verification
# =============================================================================

def test_hdf5_ontology_enforcer(tmp_path: Path) -> None:
    """Test HDF5 ontology enforcer and physically verify container attributes and datasets."""
    h5_file = tmp_path / "test_state.h5"
    enforcer = CoChemHDF5Manager(hdf5_path=h5_file)

    water_coords = [
        [0.000000000, 0.000000000, 0.000000000],
        [0.000000000, -0.757160000, 0.586260000],
        [0.000000000, 0.757160000, 0.586260000],
    ]
    valid_record = {
        "molecule_name": "water",
        "xyz_coordinates": water_coords,
        "energy": -76.4,
        "symmetry_group": "C2v",
        "LAM_TRIGGER_REQUIRED": False,
    }

    # 1. Commit record to HDF5
    enforcer.write_record("basins/water", valid_record)
    assert h5_file.exists()

    # 2. AUD-01 Physical inspection of the HDF5 container
    with h5py.File(h5_file, "r") as h5f:
        assert "basins/water" in h5f
        grp = h5f["basins/water"]

        # Assert group attributes committed correctly
        assert grp.attrs["molecule_name"] == "water"
        assert grp.attrs["energy"] == pytest.approx(-76.4)
        assert grp.attrs["symmetry_group"] == "C2v"
        assert bool(grp.attrs["LAM_TRIGGER_REQUIRED"]) is False

        # Assert dataset shape, dtype, and coordinate tensor values
        assert "xyz_coordinates" in grp
        dset = grp["xyz_coordinates"]
        assert dset.shape == (3, 3)
        assert dset.dtype == np.float64
        assert np.allclose(dset[...], np.array(water_coords, dtype=np.float64))

    # 3. Overwrite verification
    perturbed_coords = [
        [0.000000000, 0.000000000, 0.010000000],
        [0.000000000, -0.760000000, 0.590000000],
        [0.000000000, 0.760000000, 0.590000000],
    ]
    updated_record = {
        "molecule_name": "water_perturbed",
        "xyz_coordinates": perturbed_coords,
        "energy": -76.385,
        "symmetry_group": "C2v",
        "LAM_TRIGGER_REQUIRED": True,
    }
    enforcer.write_record("basins/water", updated_record)

    with h5py.File(h5_file, "r") as h5f:
        grp = h5f["basins/water"]
        assert grp.attrs["molecule_name"] == "water_perturbed"
        assert grp.attrs["energy"] == pytest.approx(-76.385)
        assert bool(grp.attrs["LAM_TRIGGER_REQUIRED"]) is True
        dset = grp["xyz_coordinates"]
        assert np.allclose(dset[...], np.array(perturbed_coords, dtype=np.float64))

    # 4. Schema rejection on invalid payloads
    invalid_record = {
        "xyz_coordinates": "invalid_structure_no_lists",
    }
    with pytest.raises(ValueError, match="HDF5 metadata schema validation failed"):
        enforcer.write_record("basins/invalid", invalid_record)

    missing_energy_record = {
        "molecule_name": "water",
    }
    with pytest.raises(ValueError, match="HDF5 metadata schema validation failed"):
        enforcer.write_record("basins/missing_fields", missing_energy_record)


# =============================================================================
# AUD-03: Incomplete API Coverage of write_dataset_with_attributes
# =============================================================================

def test_write_dataset_with_attributes_basin_and_config(tmp_path: Path) -> None:
    """Test write_dataset_with_attributes for BasinRecord, CoChemConfig, and schema rejection."""
    h5_file = tmp_path / "test_attributes.h5"
    enforcer = HDF5OntologyEnforcer(hdf5_path=h5_file)

    # 1. BasinRecord payload branch
    basin_data = np.array([10.5, 20.5, 30.5], dtype=np.float64)
    basin_payload = {
        "molecule_name": "CO2-H2O",
        "energy": -228.45,
        "symmetry_group": "Cs",
        "LAM_TRIGGER_REQUIRED": True,
        "xyz_coordinates": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
    }
    enforcer.write_dataset_with_attributes(
        dataset_name="basin_sample",
        data=basin_data,
        metadata_payload=basin_payload,
        group_name="basins_archive",
    )

    with h5py.File(h5_file, "r") as h5f:
        assert "basins_archive/basin_sample" in h5f
        dset = h5f["basins_archive/basin_sample"]
        assert np.allclose(dset[...], basin_data)
        assert dset.attrs["molecule_name"] == "CO2-H2O"
        assert dset.attrs["energy"] == pytest.approx(-228.45)
        assert dset.attrs["symmetry_group"] == "Cs"
        assert bool(dset.attrs["LAM_TRIGGER_REQUIRED"]) is True

    # 2. CoChemConfig payload branch
    config_data = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    config_payload = {
        "project_name": "Argon-HCl-Campaign",
        "workflow_id": "wf_v4_pes_001",
    }
    enforcer.write_dataset_with_attributes(
        dataset_name="config_grid",
        data=config_data,
        metadata_payload=config_payload,
        group_name="method_matrix",
    )

    with h5py.File(h5_file, "r") as h5f:
        assert "method_matrix/config_grid" in h5f
        dset = h5f["method_matrix/config_grid"]
        assert np.allclose(dset[...], config_data)
        assert dset.attrs["project_name"] == "Argon-HCl-Campaign"
        assert dset.attrs["workflow_id"] == "wf_v4_pes_001"
        assert bool(dset.attrs["LAM_TRIGGER_REQUIRED"]) is False

    # 3. Overwrite existing dataset
    updated_config_data = np.array([[5.0, 6.0], [7.0, 8.0]], dtype=np.float64)
    updated_payload = {
        "project_name": "Argon-HCl-Campaign-v2",
        "workflow_id": "wf_v4_pes_002",
    }
    enforcer.write_dataset_with_attributes(
        dataset_name="config_grid",
        data=updated_config_data,
        metadata_payload=updated_payload,
        group_name="method_matrix",
    )

    with h5py.File(h5_file, "r") as h5f:
        dset = h5f["method_matrix/config_grid"]
        assert np.allclose(dset[...], updated_config_data)
        assert dset.attrs["project_name"] == "Argon-HCl-Campaign-v2"
        assert dset.attrs["workflow_id"] == "wf_v4_pes_002"

    # 4. Schema rejection on invalid metadata payload
    invalid_payload = {"unrecognized_key": "unsupported_value"}
    with pytest.raises(ValueError, match="HDF5 metadata schema validation failed"):
        enforcer.write_dataset_with_attributes(
            dataset_name="invalid_dataset",
            data=np.array([1, 2, 3]),
            metadata_payload=invalid_payload,
            group_name="method_matrix",
        )


# =============================================================================
# AUD-04: Method Matrix §8C HDF5 Store (PESStore) Compliance
# =============================================================================

def test_method_matrix_8c_pes_store_compliance(tmp_path: Path) -> None:
    """
    Test PESStore against Method Matrix §8C specification:
    - Chunked resizable storage with gzip+shuffle+fletcher32 filters.
    - Strict rejection of lossy scaleoffset filter.
    - QCSchema metadata registration and provenance stamping.
    - Idempotent todo() pattern for restartability.
    - Delta-learning pair alignment and DVR grid reshaping.
    """
    h5_path = tmp_path / "vdw_pes_campaign.h5"
    symbols = ["Ar", "H", "Cl"]
    store = PESStore(path=h5_path, complex_name="Ar-HCl", symbols=symbols)

    # 1. Physical metadata verification
    with h5py.File(h5_path, "r") as f:
        meta = f["meta"]
        assert meta.attrs["schema_name"] == "vdw_pes_campaign"
        assert int(meta.attrs["schema_version"]) == 1
        assert meta.attrs["complex"] == "Ar-HCl"
        assert int(meta.attrs["n_atoms"]) == 3
        assert json.loads(meta.attrs["symbols"]) == ["Ar", "H", "Cl"]

    # 2. QCSchema method registration
    store.register_method(
        method_id="dlpno_avtz",
        method="DLPNO-CCSD(T1)",
        basis="cc-pVTZ",
        aux_basis="def2-TZVP/C",
        program="ORCA",
        program_version="6.1",
        driver="energy",
        frozen_core=True,
        counterpoise="none",
        keywords={"TCutPNO": 1e-7, "PNO": "TightPNO", "SCF": "TightSCF"},
    )
    assert "dlpno_avtz" in store.list_methods()
    method_meta = store.get_method("dlpno_avtz")
    assert method_meta["method"] == "DLPNO-CCSD(T1)"
    assert method_meta["program"] == "ORCA"
    assert method_meta["keywords"]["TCutPNO"] == 1e-7

    # 3. Add points and verify chunked, compressed, fletcher32, resizable datasets
    coords_pt1 = [
        [0.0, 0.0, 3.8],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 1.28],
    ]
    coords_pt2 = [
        [0.0, 0.0, 4.0],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 1.28],
    ]
    energies_high = [-460.123456789, -460.123456850]
    i0 = store.add_points(
        method_id="dlpno_avtz",
        coords=[coords_pt1, coords_pt2],
        energies=energies_high,
        point_ids=["pt_0", "pt_1"],
        converged=[True, True],
        wall_s=[15.2, 16.1],
        creator="ORCA",
        version="6.1",
        routine="sp",
    )
    assert i0 == 0

    with h5py.File(h5_path, "r") as f:
        coords_ds = f["points/dlpno_avtz/coordinates"]
        energy_ds = f["points/dlpno_avtz/energy"]
        converged_ds = f["points/dlpno_avtz/converged"]
        prov_ds = f["points/dlpno_avtz/provenance"]

        # Chunking & resizability
        assert coords_ds.shape == (2, 3, 3)
        assert coords_ds.maxshape == (None, 3, 3)
        assert coords_ds.chunks is not None

        assert energy_ds.shape == (2,)
        assert energy_ds.maxshape == (None,)
        assert energy_ds.chunks is not None

        # Compression: gzip + shuffle
        assert coords_ds.compression == "gzip"
        assert coords_ds.compression_opts == 4
        assert coords_ds.shuffle is True

        assert energy_ds.compression == "gzip"
        assert energy_ds.compression_opts == 4
        assert energy_ds.shuffle is True

        # Checksum: fletcher32 on energy
        assert energy_ds.fletcher32 is True

        # Method Matrix §8C: STRICT BAN on lossy scaleoffset
        assert coords_ds.scaleoffset is None
        assert energy_ds.scaleoffset is None

        # Provenance verification
        prov_entry = json.loads(prov_ds[0].decode("utf-8") if isinstance(prov_ds[0], bytes) else prov_ds[0])
        assert prov_entry["creator"] == "ORCA"
        assert prov_entry["version"] == "6.1"

    # 4. Resizability / append verification
    coords_pt3 = [
        [0.0, 0.0, 4.2],
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 1.28],
    ]
    i1 = store.add_points(
        method_id="dlpno_avtz",
        coords=coords_pt3,
        energies=-460.123456800,
        point_ids=["pt_2"],
        converged=True,
        wall_s=14.0,
    )
    assert i1 == 2

    coords_all, energies_all = store.dataset("dlpno_avtz", converged_only=True)
    assert coords_all.shape == (3, 3, 3)
    assert len(energies_all) == 3

    # 5. Method Matrix §8C todo() restartability pattern
    wanted_ids = ["pt_0", "pt_1", "pt_2", "pt_3", "pt_4"]
    missing = store.todo("dlpno_avtz", wanted_ids)
    assert missing == ["pt_3", "pt_4"]

    # 6. Hessian storage verification
    H_matrix = np.eye(9, dtype=np.float64) * 0.05
    store.add_hessian("hess_min", H_matrix, level="DLPNO-CCSD(T1)/cc-pVTZ", geometry_ref="pt_0")

    with h5py.File(h5_path, "r") as f:
        assert "hessians/hess_min" in f
        h_ds = f["hessians/hess_min"]
        assert h_ds.shape == (9, 9)
        assert h_ds.attrs["level"] == "DLPNO-CCSD(T1)/cc-pVTZ"
        assert h_ds.attrs["geometry_ref"] == "pt_0"
        assert h_ds.compression == "gzip"
        assert h_ds.shuffle is True

    # 7. Grid registration and DVR grid reshaping
    r_axis = np.array([3.8, 4.0])
    th_axis = np.array([0.0, np.pi])
    store.register_grid("grid_r_th", {"R": r_axis, "theta": th_axis})

    with h5py.File(h5_path, "r") as f:
        assert "grids/grid_r_th" in f
        assert np.allclose(f["grids/grid_r_th/R"][...], r_axis)
        assert np.allclose(f["grids/grid_r_th/theta"][...], th_axis)

    # 8. Delta-learning pairs alignment
    store.register_method(method_id="hf_def2", method="HF", basis="def2-SVP", program="ORCA")
    energies_low = [-459.800000000, -459.800000100, -459.800000050]
    store.add_points(
        method_id="hf_def2",
        coords=[coords_pt1, coords_pt2, coords_pt3],
        energies=energies_low,
        point_ids=["pt_0", "pt_1", "pt_2"],
        converged=[True, True, True],
    )

    keys, X, dE = store.delta_pairs("hf_def2", "dlpno_avtz")
    assert keys == ["pt_0", "pt_1", "pt_2"]
    assert X.shape == (3, 3, 3)
    expected_dE = np.array(energies_all) - np.array(energies_low)
    assert np.allclose(dE, expected_dE)

    # 9. DVR grid reshaping (Method Matrix §8C)
    store.add_points(
        method_id="dlpno_avtz",
        coords=[coords_pt1, coords_pt2],
        energies=[-460.100000000, -460.200000000],
        point_ids=["grid_r_th:0", "grid_r_th:1"],
        converged=[True, True],
    )
    V_dvr = store.dvr_grid(method_id="dlpno_avtz", grid_id="grid_r_th")
    assert V_dvr.shape == (2, 2)
    assert V_dvr.flatten()[0] == pytest.approx(-460.100000000)
    assert V_dvr.flatten()[1] == pytest.approx(-460.200000000)
    assert np.isnan(V_dvr.flatten()[2])  # Uncomputed points filled with NaN to feed into todo()
    assert np.isnan(V_dvr.flatten()[3])
