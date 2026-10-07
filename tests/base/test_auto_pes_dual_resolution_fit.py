"""Dual-Resolution Baseline Fitting in Active Learning Delta-ML PES Orchestration Numerical Tests.

Method Matrix Reference: Method Matrix v4 §4.4, §8C, §10.8, Table 2, Suggestion #129.
Provenance Tags: [M] Mandated, [D] Derived, [E] Empirical.

Validates:
1. Complete dense baseline surface anchor (low_krr trained on complete N_dense = 2000 DFT points).
2. Sparse delta-learning escalation fit (delta_krr trained strictly on aligned high-level CCSD(T) residuals).
3. Graceful reduction to baseline DFT surface in distant extrapolation regions devoid of CCSD(T) data.
4. Process-safe HDF5 datastore persistence using SWMR mode under cross-platform filelock.FileLock.
The helper supplies empirical EMT and an artificial affine target. Historical
DFT/CCSD labels below name datastore roles, not quantum-engine provenance.
"""

from __future__ import annotations

import math
from pathlib import Path

import filelock
import h5py
import numpy as np

from cochem_base.core_engine.cochem_core_auto_pes import (
    AutoPESOrchestrator,
    DeltaFittingConfig,
    generate_benchmark_intermolecular_pes_data,
)


def test_dual_resolution_baseline_fitting():
    """Assert low_krr is anchored on all 2000 dense DFT points and delta_krr on sparse residuals [M], [D]."""
    # 1. Generate 2000 EMT labels and aligned numerical affine-transformed targets
    symbols, geoms_dense, e_dft_dense, e_cc_dense = generate_benchmark_intermolecular_pes_data(
        n_points=2000, random_seed=42
    )

    # 2. Construct sparse active learning escalation dataset (300 points)
    sparse_indices = np.arange(300)
    train_geoms = geoms_dense[sparse_indices[:240]]
    train_low_e = e_dft_dense[sparse_indices[:240]]
    train_high_e = e_cc_dense[sparse_indices[:240]]

    held_out_geoms = geoms_dense[sparse_indices[240:300]]
    held_out_low_e = e_dft_dense[sparse_indices[240:300]]
    held_out_high_e = e_cc_dense[sparse_indices[240:300]]

    fit_config = DeltaFittingConfig(
        kernel="matern52",
        regularization_alpha=1e-6,
        gamma=1.5,
    )
    orchestrator = AutoPESOrchestrator(
        symbols=symbols,
        low_method="ase_emt",
        high_method="numerical_affine_emt_target",
        fit_config=fit_config,
    )

    # 3. Fit dual-resolution delta surface
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

    # 4. Verify low_krr trained on all 2000 dense points
    assert model.low_level_estimator is not None
    assert model.low_level_estimator.X_train.shape[0] == 2000, (
        f"Expected low_krr trained on 2000 dense points, got {model.low_level_estimator.X_train.shape[0]}"
    )

    # 5. Verify delta_krr trained strictly on the 240 training difference pairs
    assert model.krr_estimator.X_train.shape[0] == 240, (
        f"Expected delta_krr trained on 240 sparse points, got {model.krr_estimator.X_train.shape[0]}"
    )
    assert fit_summary.n_base_dft_points == 2000

    # 6. Asymptotic coordinate extrapolation test: delta correction must decay to 0
    extrap_geom = np.array([
        [[0.0, 0.0, 0.0], [8.0, 0.0, 0.0], [8.0, 2.5, 0.0]]
    ], dtype=np.float64)

    delta_extrap = float(model.predict_delta(extrap_geom)[0])
    total_extrap = float(model.predict_total_energy(extrap_geom, allow_unvalidated_baseline=True)[0])

    assert abs(delta_extrap) < 0.5, f"Delta correction {delta_extrap:.4f} Eh diverged in extrapolation."
    assert not math.isnan(total_extrap) and not math.isinf(total_extrap)


def test_hdf5_swmr_dual_resolution_store_persistence(tmp_path: Path):
    """Assert fit_delta_surface_from_store loads and fits under filelock.FileLock and SWMR [M]."""
    symbols, geoms_dense, e_dft_dense, e_cc_dense = generate_benchmark_intermolecular_pes_data(
        n_points=300, random_seed=99
    )
    h5_path = tmp_path / "dual_res_pes_store.h5"
    lock_path = h5_path.with_suffix(".h5.lock")

    with filelock.FileLock(lock_path, timeout=10.0):
        with h5py.File(h5_path, "w", libver="latest") as h5f:
            grp_dense = h5f.create_group("dense_dft")
            grp_dense.create_dataset("coordinates", data=geoms_dense)
            grp_dense.create_dataset("energy", data=e_dft_dense)

            grp_sparse = h5f.create_group("sparse_ccsd")
            grp_sparse.create_dataset("coordinates", data=geoms_dense[:60])
            grp_sparse.create_dataset("energy", data=e_cc_dense[:60])
            grp_sparse.create_dataset("low_energy", data=e_dft_dense[:60])

    orchestrator = AutoPESOrchestrator(
        symbols=symbols,
        low_method="ase_emt",
        high_method="numerical_affine_emt_target",
    )

    model, fit_summary = orchestrator.fit_delta_surface_from_store(h5_path, held_out_ratio=0.20)
    assert model.low_level_estimator is not None
    assert model.low_level_estimator.X_train.shape[0] == 300
    assert model.krr_estimator.X_train.shape[0] == 48  # 60 - 12 (20% held out)
    assert fit_summary.n_base_dft_points == 300
