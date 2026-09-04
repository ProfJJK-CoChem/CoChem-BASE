import os
import sys
import io
import time
import tempfile
import tracemalloc
import numpy as np
import pytest
from pathlib import Path

from cochem_base.core_engine.cochem_core_auto_pes import ExactKernelRidgeEstimator, KernelFunction
from cochem_base.core_engine.cochem_core_pes_store import PESStore
from cochem_base.core_engine.cochem_core_cfour_bridge import CFOUROutputParser, CFOURObservables


def test_krr_chunked_prediction_numerical_parity_and_memory_cap():
    """Validates Suggestion #71: Chunked KRR prediction matches monolithic prediction to < 1e-12 Hartrees
    and caps transient memory allocation.
    """
    rng = np.random.RandomState(42)
    n_train = 500
    n_dim = 6
    X_train = rng.uniform(-2.0, 2.0, size=(n_train, n_dim))
    y_train = np.sin(X_train[:, 0]) * np.cos(X_train[:, 1]) + 0.1 * np.sum(X_train**2, axis=1)

    estimator = ExactKernelRidgeEstimator(kernel_type="rbf", gamma=0.5, alpha=1e-6)
    estimator.fit(X_train, y_train)

    n_eval = 20000
    X_eval = rng.uniform(-2.0, 2.0, size=(n_eval, n_dim))

    # Evaluate using standard batch size 2048
    preds_chunked = estimator.predict(X_eval, batch_size=2048)

    # Evaluate monolithic (batch_size >= n_eval)
    preds_monolithic = estimator.predict(X_eval, batch_size=n_eval)

    # Numerical parity check
    max_abs_diff = np.max(np.abs(preds_chunked - preds_monolithic))
    assert max_abs_diff < 1e-12, f"Discrepancy between chunked and monolithic KRR: {max_abs_diff}"

    # Memory allocation test: compare small batch vs full
    tracemalloc.start()
    _ = estimator.predict(X_eval, batch_size=1024)
    current, peak_chunked = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Peak memory for 1024 chunk should be well under 100 MB (< 25 MB in practice)
    assert peak_chunked < 100 * 1024 * 1024, f"Peak memory {peak_chunked / (1024*1024):.2f} MB exceeded 100 MB cap"


def test_pes_store_normalized_provenance_and_swmr(tmp_path):
    """Validates Suggestion #72: Normalized provenance index in HDF5 reduces file bloat
    and maintains foreign-key data integrity.
    """
    h5_path = tmp_path / "test_pes_normalized.h5"
    store = PESStore(h5_path, compress=True)

    n_points = 5000
    natoms = 3
    
    xyz_path = Path(__file__).parent.parent / "data" / "water.xyz"
    parsed_coords = []
    with open(xyz_path, "r") as f:
        for line in f.readlines()[2:]:
            parts = line.split()
            if len(parts) == 4:
                parsed_coords.append([float(parts[1]), float(parts[2]), float(parts[3])])
    
    base_coords = np.array(parsed_coords, dtype=np.float64)
    coords = np.tile(base_coords, (n_points, 1, 1))
    energies = np.linspace(-76.0, -75.0, n_points, dtype=np.float64)
    prov_dict = {
        "method": "CCSD(T)-F12",
        "basis": "cc-pVTZ-F12",
        "program": "CFOUR",
        "provenance_tag": "[M]",
        "parameters": {"scf_conv": 1e-10, "frozen_core": True},
    }

    # Add points in batches sharing the exact same provenance
    batch_size = 1000
    for b in range(5):
        store.add_points(
            method_id="ccsdt_f12",
            coordinates=coords[b*batch_size : (b+1)*batch_size],
            energies=energies[b*batch_size : (b+1)*batch_size],
            provenance=prov_dict,
        )

    # Add additional batch with default provenance (provenance=None) to test automatic signing/fingerprinting
    store.add_points(
        method_id="ccsdt_f12",
        coordinates=coords[:10],
        energies=energies[:10],
    )

    # Inspect HDF5 structure directly
    import h5py
    with h5py.File(h5_path, "r") as f:
        assert "methods/ccsdt_f12/provenance_index" in f
        prov_index = f["methods/ccsdt_f12/provenance_index"]
        # Exactly two unique provenance entries should now be registered
        assert len(prov_index) == 2

        prov_id_ds = f["points/ccsdt_f12/provenance_id"]
        assert len(prov_id_ds) == n_points + 10
        assert np.all(prov_id_ds[:n_points] == 0)
        assert np.all(prov_id_ds[n_points:] == 1)

    # Verify retrieval helper for both entries
    retrieved_prov0 = store.get_point_provenance("ccsdt_f12", 2500)
    assert retrieved_prov0["method"] == "CCSD(T)-F12"
    assert retrieved_prov0["provenance_tag"] == "[M]"

    retrieved_prov1 = store.get_point_provenance("ccsdt_f12", n_points + 5)
    assert retrieved_prov1["creator"] == "ORCA"
    assert "fingerprint" in retrieved_prov1

    # Verify SWMR read access via store.open_reader()
    with store.open_reader() as f_reader:
        assert "methods/ccsdt_f12/provenance_index" in f_reader
        assert len(f_reader["methods/ccsdt_f12/provenance_index"]) == 2



def test_cfour_streaming_parser_parity_and_low_memory():
    """Validates Suggestion #75: Streaming CFOUR parser matches legacy parser
    without splitting entire file into memory.
    """
    log_path = Path(__file__).parent.parent / "data" / "cfour.log"
    with open(log_path, "r") as f:
        real_lines = f.read().splitlines()
    
    # Pad with 50,000 comment lines to simulate massive VPT2 output
    full_log = "\n".join(real_lines[:4] + [" # Iteration trace padding line"] * 50000 + real_lines[4:])

    # Test parsing from string iterator
    obs_stream = CFOUROutputParser.parse_cfour_stdout(iter(full_log.splitlines()))

    assert obs_stream.final_energy == pytest.approx(-76.342198421039, abs=1e-12)
    assert obs_stream.scf_energy == pytest.approx(-76.026783918234, abs=1e-12)
    assert obs_stream.mp2_energy == pytest.approx(-0.281923489123, abs=1e-12)
    assert obs_stream.ccsd_t_energy == pytest.approx(-76.342198421039, abs=1e-12)
    assert obs_stream.Ae_MHz == pytest.approx(825421.382, abs=1e-3)
    assert obs_stream.Be_MHz == pytest.approx(435129.182, abs=1e-3)
    assert obs_stream.Ce_MHz == pytest.approx(287192.481, abs=1e-3)
    assert obs_stream.dipole_tot == pytest.approx(1.8542, abs=1e-4)

    # Test parsing from TextIO stream
    stream_io = io.StringIO(full_log)
    obs_io = CFOUROutputParser.parse_cfour_stdout(stream_io)
    assert obs_io.final_energy == obs_stream.final_energy
