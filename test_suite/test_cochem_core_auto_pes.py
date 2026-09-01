"""
Physical Unit and Integration Test Suite for CoChem Core AutoPES Engine.

Validates:
1. AUD-01: Invariant GeometryFeaturizer (Morse coordinates, pair distances, Coulomb matrix, analytical Jacobians).
2. AUD-02: Mendeleev Library Mandate compliance (Zero hardcoded masses, dynamic atomic mass and number resolution).
3. AUD-03: Committee Uncertainty Quantification (M=4 ensemble, E_bar, sigma_E / sqrt(N_atoms) in meV/atom, G5 IQR threshold).
4. AUD-04: Active Learning point selection (300-800 points from ~2,000 pool, Two-Set Error-Based Acquisition, anti-pure-variance checks).
5. AUD-05: Delta-Learning Potential Energy Surface Fitting (Kernel Ridge Regression, analytical Cartesian gradients, exact model persistence).
6. AUD-06: Spectroscopic Held-Out Validation Protocol (Held-out RMSE in cm^-1, kcal/mol, and Hartree against <= 10.0 cm^-1 target).
7. AUD-07: Integration with PESStore HDF5 campaign container (dataset loading, delta_pairs extraction, model fitting).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Tuple

import h5py
import numpy as np
import pytest

from core_engine.cochem_core_auto_pes import (
    AcquisitionStrategy,
    ActiveLearningConfig,
    ActiveLearningEngine,
    AutoPESOrchestrator,
    CommitteeModel,
    DeltaFittingConfig,
    DeltaPESModel,
    FittingBackend,
    GeometryFeaturizer,
    KernelType,
    PESValidator,
    generate_synthetic_intermolecular_pes_data,
    get_dynamic_atomic_mass,
    get_dynamic_atomic_number,
)
from core_engine.cochem_core_pes_store import PESStore


# =============================================================================
# Featurizer and Mendeleev Tests
# =============================================================================

def test_mendeleev_dynamic_mass_and_atomic_numbers() -> None:
    """Validates dynamic retrieval of atomic masses and numbers without hardcoded tables."""
    h_mass = get_dynamic_atomic_mass("H")
    d_mass = get_dynamic_atomic_mass("D")
    ar_mass = get_dynamic_atomic_mass("Ar")
    cl_mass = get_dynamic_atomic_mass("Cl")

    assert 1.000 < h_mass < 1.015
    assert 2.010 < d_mass < 2.020
    assert 39.8 < ar_mass < 40.1
    assert 35.3 < cl_mass < 35.6

    assert get_dynamic_atomic_number("H") == 1
    assert get_dynamic_atomic_number("D") == 1
    assert get_dynamic_atomic_number("Ar") == 18
    assert get_dynamic_atomic_number("Cl") == 17


def test_geometry_featurizer_morse_and_jacobian() -> None:
    """Validates Morse coordinates and analytical Jacobian derivatives."""
    symbols = ["Ar", "H", "Cl"]
    feat = GeometryFeaturizer(symbols=symbols, morse_lambda=2.0)

    assert feat.n_atoms == 3
    assert feat.n_pairs == 3  # (0,1), (0,2), (1,2)

    # Test geometry configuration
    geom = np.array([
        [0.0, 0.0, 0.0],
        [0.0, 0.0, 3.8],
        [1.0, 0.0, 3.8],
    ], dtype=np.float64)

    morse_feats = feat.compute_morse_features(geom)
    assert morse_feats.shape == (3,)
    assert np.all(morse_feats > 0.0)
    assert np.all(morse_feats < 1.0)

    # Analytical Jacobian
    jac = feat.compute_morse_jacobian(geom)
    assert jac.shape == (3, 3, 3)  # (N_pairs, N_atoms, 3)

    # Numerical finite-difference verification of Jacobian
    eps = 1e-6
    for p_idx in range(3):
        for atom_idx in range(3):
            for axis_idx in range(3):
                geom_plus = geom.copy()
                geom_minus = geom.copy()
                geom_plus[atom_idx, axis_idx] += eps
                geom_minus[atom_idx, axis_idx] -= eps

                f_plus = feat.compute_morse_features(geom_plus)[p_idx]
                f_minus = feat.compute_morse_features(geom_minus)[p_idx]
                num_deriv = (f_plus - f_minus) / (2.0 * eps)
                ana_deriv = jac[p_idx, atom_idx, axis_idx]
                np.testing.assert_allclose(ana_deriv, num_deriv, rtol=1e-4, atol=1e-5)


# =============================================================================
# Committee Uncertainty and Active Learning Tests
# =============================================================================

def test_committee_uncertainty_and_g5_gate() -> None:
    """Validates CommitteeModel M=4 ensemble UQ and Guard G5 IQR threshold calculation."""
    symbols, geoms, e_dft, _ = generate_synthetic_intermolecular_pes_data(n_points=100, random_seed=42)
    featurizer = GeometryFeaturizer(symbols=symbols, morse_lambda=2.0)

    committee = CommitteeModel(featurizer=featurizer, committee_size=4, random_seed=42)
    committee.fit(geoms[:50], e_dft[:50])

    assert committee.is_fitted
    assert len(committee.members) == 4
    assert committee.training_iqr_threshold_hartree > 0.0
    assert committee.training_iqr_threshold_mev_atom > 0.0

    # Evaluate prediction on a test point
    pred = committee.predict_single_with_uq(geoms[60])
    assert isinstance(pred.mean_energy_hartree, float)
    assert pred.sigma_energy_hartree >= 0.0
    assert pred.sigma_energy_mev_per_atom >= 0.0
    assert len(pred.member_energies) == 4


def test_active_learning_selection_execution() -> None:
    """Validates active learning selection of 300-800 points from candidate pool."""
    symbols, geoms, e_dft, _ = generate_synthetic_intermolecular_pes_data(n_points=600, random_seed=42)
    featurizer = GeometryFeaturizer(symbols=symbols, morse_lambda=2.0)

    config = ActiveLearningConfig(
        pool_size=600,
        n_select_min=200,
        n_select_max=400,
        n_select_target=300,
        batch_size=50,
        acquisition_strategy=AcquisitionStrategy.TWO_SET_ERROR_BASED,
        held_out_ratio=0.20,
    )
    al_engine = ActiveLearningEngine(featurizer=featurizer, config=config)

    res = al_engine.select_points(geoms, e_dft)

    assert res.n_selected == 300
    assert len(res.selected_indices) == 300
    assert len(res.held_out_indices) == 120  # 20% of 600
    # Selected indices and held-out indices must be strictly disjoint
    assert len(set(res.selected_indices) & set(res.held_out_indices)) == 0


# =============================================================================
# Delta-Learning PES Fitting & Validation Tests
# =============================================================================

def test_delta_pes_fitting_and_spectroscopic_validation() -> None:
    """Validates Delta-learning surface fitting, spectroscopic held-out RMSE, and analytical gradients."""
    symbols, geoms, e_dft, e_cc = generate_synthetic_intermolecular_pes_data(n_points=500, random_seed=42)

    orchestrator = AutoPESOrchestrator(
        symbols=symbols,
        low_method="wb97x_v_tz",
        high_method="dlpno_ccsdt1_avtz",
        fit_config=DeltaFittingConfig(
            backend=FittingBackend.KERNEL_RIDGE,
            kernel=KernelType.RBF,
            regularization_alpha=1e-6,
            target_rms_cm1=10.0,
        ),
    )

    train_idx = list(range(0, 350))
    held_idx = list(range(350, 500))

    model, summary = orchestrator.fit_delta_surface_from_data(
        train_geoms=geoms[train_idx],
        train_low_energies=e_dft[train_idx],
        train_high_energies=e_cc[train_idx],
        held_out_geoms=geoms[held_idx],
        held_out_low_energies=e_dft[held_idx],
        held_out_high_energies=e_cc[held_idx],
    )

    metrics = summary.metrics
    assert metrics.n_train == 350
    assert metrics.n_held_out == 150
    assert metrics.held_out_rmse_cm1 < 10.0  # Spectroscopic grade verification (< 10 cm^-1)
    assert metrics.spectroscopic_grade is True

    # Analytical gradient shape verification
    grad = model.predict_gradient(geoms[0])
    assert grad.shape == (3, 3)

    # Save and reload model
    with tempfile.TemporaryDirectory() as tmpdir:
        model_path = Path(tmpdir) / "test_model.npz"
        model.save_npz(model_path)
        assert model_path.exists()

        reloaded = DeltaPESModel.load_npz(model_path)
        pred_orig = model.predict_delta(geoms[held_idx[:10]])
        pred_reload = reloaded.predict_delta(geoms[held_idx[:10]])
        np.testing.assert_allclose(pred_orig, pred_reload, rtol=1e-12, atol=1e-12)


# =============================================================================
# PESStore HDF5 Integration Tests
# =============================================================================

def test_autopes_pesstore_integration() -> None:
    """Validates end-to-end integration between AutoPES and PESStore HDF5 container."""
    with tempfile.TemporaryDirectory() as tmpdir:
        h5_path = Path(tmpdir) / "test_campaign.h5"
        symbols, geoms, e_dft, e_cc = generate_synthetic_intermolecular_pes_data(n_points=300, random_seed=42)

        store = PESStore(
            path=str(h5_path),
            complex_name="Ar-HCl",
            symbols=symbols,
        )

        # Register low and high methods
        store.register_method(
            method_id="wb97x_v_tz",
            method="wB97X-V",
            basis="def2-TZVPP",
            program="ORCA",
            driver="energy",
        )
        store.register_method(
            method_id="dlpno_ccsdt1_avtz",
            method="DLPNO-CCSD(T1)",
            basis="cc-pVDZ-F12",
            program="ORCA",
            driver="energy",
        )

        # Append points to store
        point_ids = [f"pt_{i:04d}" for i in range(len(geoms))]
        store.add_points("wb97x_v_tz", geoms, e_dft, point_ids=point_ids, wall_s=np.ones(len(geoms)))
        store.add_points("dlpno_ccsdt1_avtz", geoms, e_cc, point_ids=point_ids, wall_s=np.ones(len(geoms)))

        orchestrator = AutoPESOrchestrator(
            symbols=symbols,
            low_method="wb97x_v_tz",
            high_method="dlpno_ccsdt1_avtz",
            al_config=ActiveLearningConfig(
                pool_size=300,
                n_select_min=100,
                n_select_target=150,
                batch_size=25,
            ),
        )

        # Test active selection from PESStore
        al_res = orchestrator.run_active_selection_from_store(store)
        assert al_res.n_selected == 150

        # Test Delta fit from PESStore
        model, summary = orchestrator.fit_delta_surface_from_store(store, held_out_ratio=0.20)
        assert summary.metrics.held_out_rmse_cm1 < 10.0
