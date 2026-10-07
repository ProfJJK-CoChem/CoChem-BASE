"""Numerical fitting contracts, distinct from quantum accuracy acceptance."""

from pathlib import Path

import h5py
import numpy as np
import pytest
from ase import Atoms, units
from ase.calculators.emt import EMT

from cochem_base.core_engine.cochem_core_auto_pes import (
    AutoPESOrchestrator,
    DeltaFittingConfig,
    DeltaPESModel,
    ExactKernelRidgeEstimator,
    FittingBackend,
    KernelType,
    generate_benchmark_intermolecular_pes_data,
)
from cochem_base.exceptions import MissingDataError


def test_emt_demo_energies_are_hartree_and_transformation_is_explicit():
    symbols, geometries, empirical, transformed = generate_benchmark_intermolecular_pes_data(1)
    atoms = Atoms(symbols, positions=geometries[0], calculator=EMT())
    energy_ev = atoms.get_potential_energy()
    assert empirical[0] == pytest.approx(energy_ev / units.Hartree, abs=1e-14)
    assert transformed[0] == pytest.approx((1.02 * energy_ev - 0.005) / units.Hartree, abs=1e-14)


def test_held_out_labels_cannot_change_either_fitted_estimator():
    symbols, geometries, empirical, transformed = generate_benchmark_intermolecular_pes_data(25)
    orchestrator = AutoPESOrchestrator(symbols=symbols, low_method="ase_emt", high_method="numerical_affine_emt_target")
    arguments = dict(
        train_geoms=geometries[:20],
        train_low_energies=empirical[:20],
        train_high_energies=transformed[:20],
        held_out_geoms=geometries[20:],
        held_out_low_energies=empirical[20:],
        held_out_high_energies=transformed[20:],
    )
    original, original_summary = orchestrator.fit_delta_surface_from_data(**arguments)
    arguments["held_out_low_energies"] = empirical[20:] + 2.0
    arguments["held_out_high_energies"] = transformed[20:] + 3.0
    altered, altered_summary = orchestrator.fit_delta_surface_from_data(**arguments)
    assert original_summary.n_base_dft_points == 20
    for name in ("low_level_estimator", "krr_estimator"):
        np.testing.assert_array_equal(getattr(original, name).weights, getattr(altered, name).weights)
    assert altered_summary.metrics.held_out_rmse_cm1 > original_summary.metrics.held_out_rmse_cm1
    assert altered_summary.metrics.spectroscopic_grade is False


def test_exact_zero_anchors_are_constraints_despite_finite_ridge():
    features = np.array([[0.0], [0.05], [0.1], [0.5], [1.0]])
    targets = np.array([0.0, 0.0, 0.0, -0.2, -0.8])
    model = ExactKernelRidgeEstimator(alpha=1e-3).fit(features, targets, zero_anchor_indices=[0, 1, 2])
    np.testing.assert_allclose(model.predict(features[:3]), 0.0, atol=1e-12, rtol=0.0)
    # Constrained predictions remain differentiable; no pointwise zero override.
    point = np.array([0.3])
    derivative = (model.predict(point + 1e-5) - model.predict(point - 1e-5)) / 2e-5
    assert model.predict_gradient_wrt_features(point)[0] == pytest.approx(derivative, abs=1e-7)


@pytest.mark.parametrize("target", [np.nan, np.inf, -np.inf])
def test_nonfinite_training_target_is_rejected(target):
    with pytest.raises(ValueError, match="finite"):
        ExactKernelRidgeEstimator().fit(np.array([[0.1], [0.2]]), np.array([0.0, target]))


@pytest.mark.parametrize("kernel", list(KernelType))
def test_kernel_gradients_use_actual_kernel_and_polynomial_degree(kernel):
    features = np.array([[0.0, 0.1], [0.05, 0.3], [0.1, 0.2], [0.5, 0.6], [1.0, 0.2]])
    targets = np.array([0.1, 0.2, 0.3, -0.2, -0.8])
    estimator = ExactKernelRidgeEstimator(kernel_type=kernel, poly_degree=7).fit(features, targets)
    point = np.array([0.3, 0.4])
    numerical = np.empty(2)
    for axis in range(2):
        step = np.zeros(2)
        step[axis] = 1e-5
        numerical[axis] = (estimator.predict(point + step) - estimator.predict(point - step)) / 2e-5
    np.testing.assert_allclose(estimator.predict_gradient_wrt_features(point), numerical, atol=1e-6, rtol=1e-5)


def test_missing_low_energy_is_not_replaced_with_high_energy(tmp_path: Path):
    symbols, geometries, empirical, transformed = generate_benchmark_intermolecular_pes_data(25)
    path = tmp_path / "missing-low.h5"
    with h5py.File(path, "w") as store:
        store["dense_dft/coordinates"] = geometries
        store["dense_dft/energy"] = empirical
        store["sparse_ccsd/coordinates"] = geometries
        store["sparse_ccsd/energy"] = transformed
    with pytest.raises(MissingDataError, match="low_energy"):
        AutoPESOrchestrator(symbols=symbols, low_method="ase_emt", high_method="numerical_affine_emt_target").fit_delta_surface_from_store(path)


def test_backend_selection_changes_estimator(tmp_path: Path):
    symbols, geometries, empirical, transformed = generate_benchmark_intermolecular_pes_data(25)
    pip = AutoPESOrchestrator(symbols=symbols, low_method="ase_emt", high_method="numerical_affine_emt_target", fit_config=DeltaFittingConfig(backend=FittingBackend.PIP_RBF))
    assert pip.featurizer.include_secondary
    polynomial = AutoPESOrchestrator(
        symbols=symbols, low_method="ase_emt", high_method="numerical_affine_emt_target",
        fit_config=DeltaFittingConfig(backend=FittingBackend.POLYNOMIAL_EXPANSION, poly_degree=7),
    )
    model, _ = polynomial.fit_delta_surface_from_data(
        train_geoms=geometries[:20], train_low_energies=empirical[:20], train_high_energies=transformed[:20],
        held_out_geoms=geometries[20:], held_out_low_energies=empirical[20:], held_out_high_energies=transformed[20:],
    )
    assert model.krr_estimator.kernel_type == KernelType.POLYNOMIAL
    assert model.low_level_estimator.poly_degree == 7
    path = model.save_npz(tmp_path / "polynomial.npz")
    restored = DeltaPESModel.load_npz(path)
    np.testing.assert_allclose(
        model.predict_total_energy(geometries, allow_unvalidated_baseline=True),
        restored.predict_total_energy(geometries, allow_unvalidated_baseline=True), atol=1e-12,
    )


def test_absolute_reference_offsets_do_not_change_fitted_energy_differences():
    symbols, geometries, empirical, transformed = generate_benchmark_intermolecular_pes_data(30)
    orchestrator = AutoPESOrchestrator(symbols=symbols, low_method="ase_emt", high_method="numerical_affine_emt_target")
    inputs = dict(
        train_geoms=geometries[:24], train_low_energies=empirical[:24], train_high_energies=transformed[:24],
        held_out_geoms=geometries[24:], held_out_low_energies=empirical[24:], held_out_high_energies=transformed[24:],
    )
    original, original_summary = orchestrator.fit_delta_surface_from_data(**inputs)
    for name in ("train_low_energies", "held_out_low_energies"):
        inputs[name] = inputs[name] + 5.0
    for name in ("train_high_energies", "held_out_high_energies"):
        inputs[name] = inputs[name] + 7.0
    shifted, shifted_summary = orchestrator.fit_delta_surface_from_data(**inputs)
    np.testing.assert_allclose(shifted.predict_delta(geometries) - 2.0, original.predict_delta(geometries), atol=1e-9)
    assert shifted_summary.metrics.held_out_rmse_cm1 == pytest.approx(original_summary.metrics.held_out_rmse_cm1, abs=1e-5)
    assert original_summary.model_parameters["energy_reference"] == "absolute"
    assert not original.krr_estimator.asymptotic_zero


def test_declared_interaction_reference_retains_zero_boundary_constraints():
    orchestrator = AutoPESOrchestrator(
        symbols=["H", "H"], fit_config=DeltaFittingConfig(energy_reference="interaction_zero_asymptote"),
    )
    estimator = orchestrator._surface_estimator()
    assert estimator.asymptotic_zero
    features = np.array([[0.0], [0.05], [0.1], [0.5], [1.0]])
    targets = np.array([0.0, -0.03, -0.1, -0.2, -0.8])
    estimator.fit(features, targets)
    assert estimator.y_mean == 0.0
    assert estimator.predict(features[0]) == pytest.approx(0.0, abs=1e-12)
