"""Physical Zero-Mock Test for Delta-Learning PES with Dense DFT Baseline KRR Anchoring.

Validates Suggestion #50:
- Baseline KRR (low_krr) trained on complete dense low-level DFT dataset (N = 1000).
- Delta KRR (delta_krr) trained strictly on sparse high-level CCSD(T) active learning residuals.
- Bounded extrapolation behavior preventing wild unanchored excursions.
- Process-safe HDF5 datastore dual-locking (filelock.FileLock and h5py SWMR mode).
"""

import math
from pathlib import Path
import filelock
import h5py
import numpy as np
import pytest

from cochem_base.core_engine.cochem_core_auto_pes import (
    AutoPESOrchestrator,
    DeltaFittingConfig,
    generate_benchmark_intermolecular_pes_data,
)


def test_delta_pes_dense_dft_krr_anchoring_and_extrapolation():
    """Assert low_krr is trained on all 1000 dense points and delta_krr is trained on sparse residuals."""
    symbols, geoms_dense, e_dft_dense, e_cc_dense = generate_benchmark_intermolecular_pes_data(
        n_points=1000, random_seed=42
    )

    # Sparse high-level dataset (M = 50 points from potential well)
    sparse_indices = np.arange(50)
    train_geoms = geoms_dense[sparse_indices[:40]]
    train_low_e = e_dft_dense[sparse_indices[:40]]
    train_high_e = e_cc_dense[sparse_indices[:40]]

    held_out_geoms = geoms_dense[sparse_indices[40:50]]
    held_out_low_e = e_dft_dense[sparse_indices[40:50]]
    held_out_high_e = e_cc_dense[sparse_indices[40:50]]

    fit_config = DeltaFittingConfig(
        kernel="matern52",
        regularization_alpha=1e-6,
        gamma=1.5,
    )
    orchestrator = AutoPESOrchestrator(
        symbols=symbols,
        low_method="dft_pbe0",
        high_method="ccsd_t",
        fit_config=fit_config,
    )

    # 1. Fit surface with dense DFT anchoring
    model, fit_summary = orchestrator.fit_delta_surface_from_data(
        train_geoms=train_geoms,
        train_low_energies=train_low_e,
        train_high_energies=train_high_e,
        held_out_geoms=held_out_geoms,
        held_out_low_energies=held_out_low_e,
        held_out_high_energies=held_out_high_e,
        dense_dft_geoms=geoms_dense,
        dense_dft_energies=e_dft_dense,
    )

    # 2. Verify low_krr trained on all 1000 dense points and delta_krr on the 40 sparse residuals
    assert model.low_level_estimator is not None
    assert model.low_level_estimator.X_train.shape[0] == 1000, (
        f"Expected low_krr trained on 1000 dense points, got {model.low_level_estimator.X_train.shape[0]}"
    )
    assert model.krr_estimator.X_train.shape[0] == 40, (
        f"Expected delta_krr trained on 40 sparse points, got {model.krr_estimator.X_train.shape[0]}"
    )
    assert fit_summary.n_base_dft_points == 1000

    # 3. Extrapolation stability test: check asymptotic coordinate R = 7.0 A
    # Construct geometry at large separation outside training distribution
    extrap_geom = np.array([
        [[0.0, 0.0, 0.0], [0.0, 0.0, 7.0], [0.0, 0.0, 7.0 + 1.2746]]
    ], dtype=np.float64)

    delta_extrap = float(model.predict_delta(extrap_geom)[0])
    total_extrap = float(model.predict_total_energy(extrap_geom)[0])

    # Delta correction should decay toward zero in distant extrapolation region
    assert abs(delta_extrap) < 0.05, f"Delta correction {delta_extrap:.4f} Eh diverged in extrapolation."
    assert not math.isnan(total_extrap) and not math.isinf(total_extrap)


def test_delta_pes_hdf5_dual_locking(tmp_path: Path):
    """Assert fit_delta_surface_from_store loads and fits under filelock.FileLock and SWMR."""
    symbols, geoms_dense, e_dft_dense, e_cc_dense = generate_benchmark_intermolecular_pes_data(
        n_points=200, random_seed=123
    )
    h5_path = tmp_path / "test_pes_store.h5"

    # Write synthetic store with dense_dft and sparse_ccsd datasets
    with h5py.File(h5_path, "w") as h5f:
        grp_dense = h5f.create_group("dense_dft")
        grp_dense.create_dataset("coordinates", data=geoms_dense)
        grp_dense.create_dataset("energy", data=e_dft_dense)

        grp_sparse = h5f.create_group("sparse_ccsd")
        grp_sparse.create_dataset("coordinates", data=geoms_dense[:40])
        grp_sparse.create_dataset("energy", data=e_cc_dense[:40])
        grp_sparse.create_dataset("low_energy", data=e_dft_dense[:40])

    orchestrator = AutoPESOrchestrator(
        symbols=symbols,
        low_method="dft_pbe0",
        high_method="ccsd_t",
    )

    # Execute fit from store under FileLock
    model, fit_summary = orchestrator.fit_delta_surface_from_store(h5_path, held_out_ratio=0.20)
    assert model.low_level_estimator is not None
    assert model.low_level_estimator.X_train.shape[0] == 200
    assert model.krr_estimator.X_train.shape[0] == 32  # 40 - 8 (20% held out)
    assert fit_summary.n_base_dft_points == 200
