"""
Test Energy Unit Normalization & SWMR HDF5 Storage Concurrency
SRS Chunk 09, Suggestion #83 (Method Matrix v4 §8C)
Zero-Mock compliant: Real HDF5 file creation, real multithreaded writes, scipy physical constants.
"""
import concurrent.futures
import os
import tempfile

import h5py
import numpy as np
import scipy.constants
from cascade_engine.cochem_cascade_hdf5 import write_tier_data

from cochem_base.data.cochem_base_pes_store import PESStore


def test_write_tier_data_energy_normalization_ev_to_hartree():
    """Pass ASE energy output in eV and assert committed value equals -100.0 / Hartree_in_eV."""
    hartree_in_ev = scipy.constants.physical_constants["Hartree energy in eV"][0]
    energy_input_ev = -100.0
    expected_hartree = energy_input_ev / hartree_in_ev

    with tempfile.TemporaryDirectory() as tmpdir:
        h5_path = os.path.join(tmpdir, "cascade_test.h5")

        write_tier_data(
            dest=h5_path,
            geom_id="pt_water_dimer",
            tier_id="T1",
            energy=energy_input_ev,
            energy_is_ev=True,
        )

        with h5py.File(h5_path, "r") as f:
            stored_energy_dataset = f["pt_water_dimer/T1/energy"][()]
            stored_energy_attr = f["pt_water_dimer/T1"].attrs["electronic_energy_hartree"]

            assert abs(stored_energy_dataset - expected_hartree) < 1e-12
            assert abs(stored_energy_attr - expected_hartree) < 1e-12


def test_pes_store_swmr_concurrent_writes():
    """Launch concurrent worker writes against PESStore and assert zero write contention errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        h5_path = os.path.join(tmpdir, "pes_store_concurrency.h5")
        store = PESStore(h5_path, timeout=30.0, swmr=True)

        n_workers = 8
        n_points_per_worker = 5

        def worker_task(worker_id: int):
            for i in range(n_points_per_worker):
                pt_id = f"worker_{worker_id}_pt_{i}"
                ev_val = -50.0 - (worker_id * 10 + i)
                coords = np.array([
                    [0.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0 + 0.05 * (worker_id + i)]
                ])
                store.write_point(
                    point_id=pt_id,
                    energy_ev=ev_val,
                    coordinates=coords,
                    tier="T1"
                )
            return worker_id

        with concurrent.futures.ThreadPoolExecutor(max_workers=n_workers) as pool:
            futures = [pool.submit(worker_task, wid) for wid in range(n_workers)]
            completed = [f.result() for f in concurrent.futures.as_completed(futures)]

        assert len(completed) == n_workers

        total_points = store.list_points()
        assert len(total_points) == n_workers * n_points_per_worker

        pt_data = store.read_point("worker_0_pt_0")
        hartree_in_ev = scipy.constants.physical_constants["Hartree energy in eV"][0]
        expected_ha = -50.0 / hartree_in_ev
        assert abs(pt_data["energy_hartree"] - expected_ha) < 1e-10
