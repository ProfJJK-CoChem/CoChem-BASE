"""CoChem-TOPOS: Test CODATA 2022 Energy Normalization and Thread-Safe HDF5 Concurrency.

Compliant with Method Matrix v4 §4.4, §8C, Anti-Spoofing Protocol v2, and Zero-Mock Mandate.
Verifies Deliverable 4:
1. Normalization of ASE potential energies (eV -> Hartree via CODATA 2022).
2. Dynamic CODATA 2022 conversion: 27.211386245988 eV / Hartree [M].
3. Safe cross-platform file locking via filelock.FileLock preventing database corruption.
"""

import os
import subprocess
import sys
from pathlib import Path

import h5py
import pytest
import scipy.constants

from cascade_engine.cochem_cascade_hdf5 import CascadeHDF5Serializer


def test_codata_energy_normalization_ev_to_hartree(tmp_path):
    """Verify that energies passed in eV are stored in Hartree normalized via CODATA 2022."""
    h5_path = tmp_path / "test_energy.h5"
    serializer = CascadeHDF5Serializer(h5_path)

    # Physical potential energy of water monomer from semiempirical evaluation (eV)
    energy_ev = -14.285321
    codata_factor = scipy.constants.value("Hartree energy in eV")
    assert pytest.approx(codata_factor, rel=1e-9) == 27.211386245988

    expected_hartree = float(energy_ev / codata_factor)

    # Pass energy_ev explicitly to write_tier_data
    serializer.write_tier_data(
        geom_id="mol_01",
        tier_id="T1",
        energy_ev=energy_ev,
        geometry="3\nWater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n",
    )

    with h5py.File(h5_path, "r", swmr=True) as f:
        stored_hartree = float(f["mol_01"]["T1"].attrs["electronic_energy_hartree"])
        dataset_hartree = float(f["mol_01"]["T1"]["energy"][()])

    assert pytest.approx(stored_hartree, rel=1e-7) == expected_hartree
    assert pytest.approx(dataset_hartree, rel=1e-7) == expected_hartree


def test_concurrent_multiprocess_hdf5_filelocking(tmp_path):
    """Verify that concurrent worker processes writing to the same HDF5 store

    synchronize safely via filelock.FileLock without corruption or BlockingIOError.
    """
    h5_path = tmp_path / "concurrent_test.h5"
    serializer = CascadeHDF5Serializer(h5_path)

    # Worker script to write 5 entries
    worker_code = f"""
import sys
from pathlib import Path
repo_base = Path(r"D:\\__CoChem\\GitHub-Repo\\CoChem-BASE")
repo_topos = Path(r"D:\\__CoChem\\GitHub-Repo\\CoChem-TOPOS")
if str(repo_topos) not in sys.path:
    sys.path.insert(0, str(repo_topos))
if str(repo_base / "src") not in sys.path:
    sys.path.insert(0, str(repo_base / "src"))
from cascade_engine.cochem_cascade_hdf5 import CascadeHDF5Serializer


h5_path = Path(r"{h5_path}")
worker_id = sys.argv[1]
serializer = CascadeHDF5Serializer(h5_path)

for i in range(5):
    serializer.write_tier_data(
        geom_id=f"geom_{{worker_id}}_{{i}}",
        tier_id="T1",
        energy_ev=-15.0 - (i * 0.1),
    )
"""

    p1 = subprocess.Popen(
        [sys.executable, "-c", worker_code, "w1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    p2 = subprocess.Popen(
        [sys.executable, "-c", worker_code, "w2"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    out1, err1 = p1.communicate(timeout=60)
    out2, err2 = p2.communicate(timeout=60)

    assert p1.returncode == 0, f"Worker 1 failed: {err1.decode()}"
    assert p2.returncode == 0, f"Worker 2 failed: {err2.decode()}"

    # Verify all 10 entries were successfully written to HDF5
    with h5py.File(h5_path, "r", swmr=True) as f:
        keys = list(f.keys())
        w1_keys = [k for k in keys if k.startswith("geom_w1_")]
        w2_keys = [k for k in keys if k.startswith("geom_w2_")]
        assert len(w1_keys) == 5
        assert len(w2_keys) == 5
